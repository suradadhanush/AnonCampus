"""
AnonCampus Scoring Engine — fully hardened

Formula:
  R' = log(1 + reports)
  S' = log(1 + supports)
  C' = 1 + 0.1 * context_count
  D  = min(1, d/4 + y/4) * (1 - p_max)   [d=unique depts, y=unique years]
  Confidence = sigmoid(0.35R' + 0.2S' + 0.1C' + 0.15D + 0.2Sev) * W'
  Visibility = 0.4C + 0.25Sev + 0.2Recency + 0.15Scope
  Recency    = exp(-0.05 * hours_since_last_activity)

Diversity fix: uses academic_year (not year_of_study). Users missing
department/year are excluded from diversity calculation (not counted as Unknown).

Explainability: every compute returns a reason dict alongside the score.
"""
import math
from typing import List, Optional, Tuple, Dict, Any
from app.core.config import settings


# ── Math primitives ───────────────────────────────────────────────────────────

def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ── Diversity ─────────────────────────────────────────────────────────────────

def compute_diversity_score(
    departments: List[Optional[str]],
    years: List[Optional[int]],
) -> Tuple[float, bool, Dict[str, Any]]:
    """
    Returns (diversity_score, is_valid, explanation_dict).

    Users with None department or None year are EXCLUDED from calculation
    (not padded as Unknown — that would corrupt the diversity signal).

    Rules:
      >= 2 unique departments
      >= 2 unique academic years
      no single group > 60% of valid reporters
    """
    valid_depts = [d for d in departments if d and d != "Unknown"]
    valid_years = [y for y in years if y is not None]

    # Use whichever set is smaller as the binding constraint
    n = min(len(valid_depts), len(valid_years)) if valid_depts and valid_years else 0

    if n == 0:
        return 0.0, False, {"reason": "insufficient_metadata", "valid_reporters": 0}

    dept_counts: Dict[str, int] = {}
    for d in valid_depts:
        dept_counts[d] = dept_counts.get(d, 0) + 1

    year_counts: Dict[int, int] = {}
    for y in valid_years:
        year_counts[y] = year_counts.get(y, 0) + 1

    unique_depts = len(dept_counts)
    unique_years = len(year_counts)
    total = len(valid_depts)
    p_max = max(dept_counts.values()) / total if total > 0 else 1.0
    dominant_dept = max(dept_counts, key=dept_counts.get) if dept_counts else "N/A"

    is_valid = (
        unique_depts >= settings.DIVERSITY_MIN_DEPARTMENTS
        and unique_years >= settings.DIVERSITY_MIN_YEARS
        and p_max <= settings.DIVERSITY_MAX_GROUP_PERCENT
    )

    d_score = min(1.0, unique_depts / 4.0 + unique_years / 4.0) * (1.0 - p_max)
    d_score = max(0.0, d_score)

    explanation = {
        "unique_departments": unique_depts,
        "unique_years": unique_years,
        "dominant_group_pct": round(p_max * 100, 1),
        "dominant_dept": dominant_dept,
        "valid_reporters": total,
        "is_valid": is_valid,
    }
    if not is_valid:
        if unique_depts < settings.DIVERSITY_MIN_DEPARTMENTS:
            explanation["fail_reason"] = f"need >={settings.DIVERSITY_MIN_DEPARTMENTS} depts, have {unique_depts}"
        elif unique_years < settings.DIVERSITY_MIN_YEARS:
            explanation["fail_reason"] = f"need >={settings.DIVERSITY_MIN_YEARS} years, have {unique_years}"
        else:
            explanation["fail_reason"] = f"dominant group {p_max*100:.0f}% exceeds 60% cap"

    return d_score, is_valid, explanation


# ── Confidence ────────────────────────────────────────────────────────────────

def compute_confidence_score(
    report_count: int,
    support_count: int,
    context_count: int,
    diversity_score: float,
    diversity_valid: bool,
    severity: float,
    trust_weight: float,
) -> Tuple[float, Dict[str, Any]]:
    """
    Returns (confidence_score, explanation_dict).
    If diversity invalid → confidence = 0.0 (hard rule, no bypass).
    """
    if not diversity_valid:
        return 0.0, {
            "confidence": 0.0,
            "reason": "diversity_invalid",
            "reports": report_count,
            "supports": support_count,
        }

    r_prime = math.log(1 + report_count)
    s_prime = math.log(1 + support_count)
    c_prime = 1 + 0.1 * context_count
    w_prime = max(settings.TRUST_MIN, min(settings.TRUST_MAX, trust_weight))

    raw = (
        settings.SCORE_WEIGHT_REPORTS   * r_prime
        + settings.SCORE_WEIGHT_SUPPORTS  * s_prime
        + settings.SCORE_WEIGHT_CONTEXT   * c_prime
        + settings.SCORE_WEIGHT_DIVERSITY * diversity_score
        + settings.SCORE_WEIGHT_SEVERITY  * severity
    )

    confidence = sigmoid(raw) * w_prime

    explanation = {
        "confidence": round(confidence, 4),
        "reports": report_count,
        "supports": support_count,
        "contexts": context_count,
        "r_prime": round(r_prime, 4),
        "s_prime": round(s_prime, 4),
        "c_prime": round(c_prime, 4),
        "diversity_score": round(diversity_score, 4),
        "severity": round(severity, 4),
        "trust_weight": round(w_prime, 4),
        "raw_sigmoid_input": round(raw, 4),
    }
    return confidence, explanation


# ── Visibility / Ranking ──────────────────────────────────────────────────────

def compute_visibility_score(
    confidence: float,
    severity: float,
    hours_since_last_activity: float,
    scope: float,
) -> float:
    recency = math.exp(-settings.RANK_RECENCY_DECAY * hours_since_last_activity)
    return (
        settings.RANK_CONFIDENCE_WEIGHT * confidence
        + settings.RANK_SEVERITY_WEIGHT  * severity
        + settings.RANK_RECENCY_WEIGHT   * recency
        + settings.RANK_SCOPE_WEIGHT     * scope
    )


def compute_scope(report_count: int, unique_departments: int, unique_years: int) -> float:
    return min(1.0,
        (report_count / 20.0)       * 0.5
        + (unique_departments / 10.0) * 0.3
        + (unique_years / 4.0)        * 0.2
    )


# ── Governance ────────────────────────────────────────────────────────────────

def check_escalation(
    report_count: int,
    support_count: int,
    diversity_valid: bool,
    severity: float,
) -> Tuple[bool, Optional[str]]:
    """
    Override path:  severity >= 0.85 AND reports >= 2  → immediate escalation
    Normal path:    reports >= 5 AND supports >= 8 AND diversity valid
    Returns (should_escalate, escalation_type)
    """
    if (severity >= settings.OVERRIDE_SEVERITY_THRESHOLD
            and report_count >= settings.OVERRIDE_MIN_REPORTS):
        return True, "override"

    if (report_count >= settings.ESCALATION_MIN_REPORTS
            and support_count >= settings.ESCALATION_MIN_SUPPORTS
            and diversity_valid):
        return True, "normal"

    return False, None


# ── Trust ─────────────────────────────────────────────────────────────────────

def update_trust_score(current_trust: float, event: str) -> float:
    """
    event: "valid_participation" | "correct_feedback" | "bad_behavior" | "daily_decay"
    """
    delta_map = {
        "valid_participation": settings.TRUST_VALID_PARTICIPATION,
        "correct_feedback":    settings.TRUST_CORRECT_FEEDBACK,
        "bad_behavior":        settings.TRUST_BAD_BEHAVIOR,
    }
    if event == "daily_decay":
        new_trust = current_trust * settings.TRUST_DAILY_DECAY
    else:
        delta = delta_map.get(event, 0.0)
        new_trust = current_trust + delta

    return max(settings.TRUST_MIN, min(settings.TRUST_MAX, new_trust))


def compute_average_trust_weight(trust_scores: List[float]) -> float:
    return sum(trust_scores) / len(trust_scores) if trust_scores else 1.0
