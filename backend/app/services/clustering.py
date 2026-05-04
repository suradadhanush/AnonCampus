"""
Clustering service — Hugging Face Inference API for embeddings
Falls back to TF-IDF/Jaccard if API unavailable
No local model download, works on 512MB RAM free tier
"""
import time
import logging
import re
import os
import json
from typing import List, Optional, Tuple

import httpx
import asyncio
from app.core.config import settings

logger = logging.getLogger("anoncampus.clustering")

HF_API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
MAX_RETRIES = 2
TIMEOUT = 5.0


async def get_embedding_async(text: str) -> Optional[List[float]]:
    """Get embedding from HuggingFace API — async version for FastAPI"""
    if not HF_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {HF_API_KEY}"},
                json={"inputs": text[:512]},  # HF limit
            )
            if resp.status_code == 200:
                data = resp.json()
                # HF returns list of lists for sentence-transformers
                if isinstance(data, list) and len(data) > 0:
                    if isinstance(data[0], list):
                        return data[0]
                    return data
            elif resp.status_code == 503:
                # Model loading — wait and retry once
                await asyncio.sleep(2)
                resp2 = await client.post(
                    HF_API_URL,
                    headers={"Authorization": f"Bearer {HF_API_KEY}"},
                    json={"inputs": text[:512]},
                )
                if resp2.status_code == 200:
                    data = resp2.json()
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], list):
                            return data[0]
                        return data
    except Exception as e:
        logger.warning(f"HF embedding failed: {e}")
    return None


def get_embedding_sync(text: str) -> Optional[List[float]]:
    """Sync version for Celery tasks"""
    if not HF_API_KEY:
        return None
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {HF_API_KEY}"},
                json={"inputs": text[:512]},
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    if isinstance(data[0], list):
                        return data[0]
                    return data
    except Exception as e:
        logger.warning(f"HF sync embedding failed: {e}")
    return None


# Keep get_embedding as sync wrapper (used by issue_service)
def get_embedding(text: str) -> Optional[List[float]]:
    return get_embedding_sync(text)


def cosine_score(vec_a: List[float], vec_b: List[float]) -> float:
    try:
        import math
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = math.sqrt(sum(a * a for a in vec_a))
        mag_b = math.sqrt(sum(b * b for b in vec_b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
    except Exception:
        return 0.0


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Fallback when embeddings unavailable"""
    words_a = set(re.findall(r'\w+', text_a.lower()))
    words_b = set(re.findall(r'\w+', text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def determine_cluster_action(
    issue_embedding: Optional[List[float]],
    issue_text: str,
    cluster_candidates: List[Tuple[int, Optional[List[float]], str]],
) -> Tuple[str, Optional[int], float]:
    if not cluster_candidates:
        return "new", None, 0.0

    best_score = 0.0
    best_cluster_id = None

    for cluster_id, c_embedding, c_title in cluster_candidates:
        if issue_embedding and c_embedding:
            score = cosine_score(issue_embedding, c_embedding)
        else:
            score = jaccard_similarity(issue_text, c_title)

        if score > best_score:
            best_score = score
            best_cluster_id = cluster_id

    if best_score >= settings.CLUSTER_SAME_THRESHOLD:
        return "same", best_cluster_id, best_score
    elif best_score >= settings.CLUSTER_CONDITIONAL_THRESHOLD:
        return "conditional", best_cluster_id, best_score
    else:
        return "new", None, best_score


def update_centroid(
    current: Optional[List[float]],
    new_vec: Optional[List[float]],
    new_count: int,
) -> Optional[List[float]]:
    if not new_vec or not current:
        return current or new_vec
    try:
        updated = [(c * (new_count - 1) + n) / new_count
                   for c, n in zip(current, new_vec)]
        mag = sum(x * x for x in updated) ** 0.5
        if mag > 0:
            updated = [x / mag for x in updated]
        return updated
    except Exception:
        return current


def classify_category(text: str) -> str:
    text_lower = text.lower()
    categories = {
        "infrastructure": ["wifi", "internet", "lab", "computer", "facility",
                           "building", "water", "electricity", "maintenance", "toilet", "power"],
        "academics":      ["exam", "syllabus", "teacher", "faculty", "lecture",
                           "assignment", "marks", "result", "timetable", "course", "grade"],
        "administration": ["fee", "scholarship", "admission", "certificate",
                           "id card", "hostel", "mess", "library", "office"],
        "safety":         ["harassment", "ragging", "safety", "security",
                           "threat", "bully", "abuse", "violence", "danger"],
        "transport":      ["bus", "transport", "vehicle", "route", "cab", "auto"],
        "sports":         ["ground", "sports", "gym", "field", "court", "cricket", "football"],
    }
    scores = {cat: sum(1 for kw in kws if kw in text_lower)
              for cat, kws in categories.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def estimate_severity(text: str) -> float:
    text_lower = text.lower()
    score = 0.5
    high = ["urgent", "immediate", "dangerous", "harassment", "ragging",
            "threat", "abuse", "critical", "emergency", "violence", "health"]
    medium = ["serious", "broken", "failing", "unable", "denied", "unfair", "delay"]
    for kw in high:
        if kw in text_lower:
            score = min(1.0, score + 0.15)
    for kw in medium:
        if kw in text_lower:
            score = min(1.0, score + 0.05)
    return round(score, 2)
