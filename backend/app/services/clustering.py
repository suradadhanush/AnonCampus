Clustering service — production safe
NLP model and sklearn are optional. Falls back to keyword matching if unavailable.

import time
import logging
import re
from typing import List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger("anoncampus.clustering")

_model = None
_sklearn_available = False

try:
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
    _sklearn_available = True
except ImportError:
    logger.warning("numpy/sklearn not available — using keyword fallback")

MAX_INFERENCE_SECONDS = 1.5


def get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentence transformer loaded")
        except Exception as e:
            logger.warning(f"Sentence transformer unavailable: {e}")
            _model = "fallback"
    return _model


def get_embedding(text: str) -> Optional[List[float]]:
    if not _sklearn_available:
        return None
    try:
        model = get_model()
        if model == "fallback":
            return None
        start = time.monotonic()
        embedding = model.encode(text, normalize_embeddings=True)
        elapsed = time.monotonic() - start
        if elapsed > MAX_INFERENCE_SECONDS:
            logger.warning(f"Embedding took {elapsed:.2f}s")
        return embedding.tolist()
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
        return None


def cosine_score(vec_a: List[float], vec_b: List[float]) -> float:
    if not _sklearn_available:
        return 0.0
    try:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
        a = np.array(vec_a, dtype=np.float32).reshape(1, -1)
        b = np.array(vec_b, dtype=np.float32).reshape(1, -1)
        return float(sk_cosine(a, b)[0][0])
    except Exception:
        return 0.0


def tfidf_similarity(text_a: str, text_b: str) -> float:
    """Keyword overlap fallback — no sklearn needed"""
    words_a = set(re.findall(r'\w+', text_a.lower()))
    words_b = set(re.findall(r'\w+', text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)  # Jaccard similarity


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
        if issue_embedding and c_embedding and _sklearn_available:
            score = cosine_score(issue_embedding, c_embedding)
        else:
            score = tfidf_similarity(issue_text, c_title)

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
    if not _sklearn_available or not new_vec:
        return current
    if not current:
        return new_vec
    try:
        import numpy as np
        c = np.array(current, dtype=np.float32)
        n = np.array(new_vec, dtype=np.float32)
        updated = (c * (new_count - 1) + n) / new_count
        norm = np.linalg.norm(updated)
        if norm > 0:
            updated = updated / norm
        return updated.tolist()
    except Exception:
        return current


def classify_category(text: str) -> str:
    text_lower = text.lower()
    categories = {
        "infrastructure": ["wifi", "internet", "lab", "computer", "facility",
                           "building", "water", "electricity", "maintenance", "toilet"],
        "academics":      ["exam", "syllabus", "teacher", "faculty", "lecture",
                           "assignment", "marks", "result", "timetable", "course"],
        "administration": ["fee", "scholarship", "admission", "certificate",
                           "id card", "hostel", "mess", "library"],
        "safety":         ["harassment", "ragging", "safety", "security",
                           "threat", "bully", "abuse", "violence"],
        "transport":      ["bus", "transport", "vehicle", "route", "cab"],
        "sports":         ["ground", "sports", "gym", "field", "court"],
    }
    scores = {cat: sum(1 for kw in kws if kw in text_lower)
              for cat, kws in categories.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def estimate_severity(text: str) -> float:
    text_lower = text.lower()
    score = 0.5
    high = ["urgent", "immediate", "dangerous", "harassment", "ragging",
            "threat", "abuse", "critical", "emergency", "violence"]
    medium = ["serious", "broken", "failing", "unable", "denied", "unfair"]
    for kw in high:
        if kw in text_lower:
            score = min(1.0, score + 0.15)
    for kw in medium:
        if kw in text_lower:
            score = min(1.0, score + 0.05)
    return round(score, 2)
