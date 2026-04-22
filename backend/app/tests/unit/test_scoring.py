"""
Unit tests — scoring engine
Target: ≥80% branch coverage for scoring.py
"""
import math
import pytest
from app.services.scoring import (
    sigmoid, compute_diversity_score, compute_confidence_score,
    compute_visibility_score, compute_scope, check_escalation,
    update_trust_score, compute_average_trust_weight,
)


# ── sigmoid ───────────────────────────────────────────────────────────────────

def test_sigmoid_zero():
    assert abs(sigmoid(0) - 0.5) < 1e-9

def test_sigmoid_large_positive():
    assert sigmoid(100) > 0.999

def test_sigmoid_large_negative():
    assert sigmoid(-100) < 0.001


# ── diversity ─────────────────────────────────────────────────────────────────

def test_diversity_valid():
    depts = ["CSE", "ECE", "MECH", "CSE"]
    years = [1, 2, 3, 1]
    score, valid, expl = compute_diversity_score(depts, years)
    assert valid is True
    assert 0.0 < score <= 1.0
    assert expl["unique_departments"] == 3
    assert expl["unique_years"] == 3

def test_diversity_one_department_fails():
    depts = ["CSE", "CSE", "CSE"]
    years = [1, 2, 3]
    score, valid, expl = compute_diversity_score(depts, years)
    assert valid is False
    assert "fail_reason" in expl

def test_diversity_dominant_group_fails():
    # 4 out of 5 from same dept = 80% > 60% cap
    depts = ["CSE", "CSE", "CSE", "CSE", "ECE"]
    years = [1, 2, 1, 2, 3]
    score, valid, expl = compute_diversity_score(depts, years)
    assert valid is False
    assert expl["dominant_group_pct"] == 80.0

def test_diversity_excludes_none_values():
    # None/Unknown should be excluded, not counted
    depts = ["CSE", None, "ECE", None]
    years = [1, None, 2, None]
    score, valid, expl = compute_diversity_score(depts, years)
    assert expl["valid_reporters"] == 2  # only 2 valid

def test_diversity_all_none_invalid():
    score, valid, expl = compute_diversity_score([None, None], [None, None])
    assert valid is False
    assert score == 0.0

def test_diversity_empty():
    score, valid, expl = compute_diversity_score([], [])
    assert valid is False
    assert score == 0.0


# ── confidence ────────────────────────────────────────────────────────────────

def test_confidence_zero_when_diversity_invalid():
    conf, expl = compute_confidence_score(
        report_count=10, support_count=20, context_count=5,
        diversity_score=0.0, diversity_valid=False,
        severity=0.9, trust_weight=1.5,
    )
    assert conf == 0.0
    assert expl["reason"] == "diversity_invalid"

def test_confidence_increases_with_reports():
    base_conf, _ = compute_confidence_score(5, 5, 0, 0.5, True, 0.5, 1.0)
    more_conf, _ = compute_confidence_score(20, 5, 0, 0.5, True, 0.5, 1.0)
    assert more_conf > base_conf

def test_confidence_trust_weight_scales():
    conf_low, _  = compute_confidence_score(5, 5, 0, 0.5, True, 0.5, 0.5)
    conf_high, _ = compute_confidence_score(5, 5, 0, 0.5, True, 0.5, 2.0)
    assert conf_high > conf_low

def test_confidence_bounded():
    conf, _ = compute_confidence_score(1000, 1000, 100, 1.0, True, 1.0, 2.0)
    assert conf <= 2.0  # sigmoid * max_trust = at most ~2.0

def test_confidence_returns_explanation():
    _, expl = compute_confidence_score(5, 8, 2, 0.6, True, 0.7, 1.0)
    assert "reports" in expl
    assert "r_prime" in expl
    assert "trust_weight" in expl


# ── visibility ────────────────────────────────────────────────────────────────

def test_visibility_recent_higher():
    v_now  = compute_visibility_score(0.7, 0.6, 0.0, 0.5)
    v_old  = compute_visibility_score(0.7, 0.6, 72.0, 0.5)
    assert v_now > v_old

def test_visibility_range():
    v = compute_visibility_score(0.8, 0.8, 1.0, 0.8)
    assert 0.0 <= v <= 1.5  # upper bound based on weights summing to 1


# ── scope ─────────────────────────────────────────────────────────────────────

def test_scope_bounded():
    s = compute_scope(100, 10, 4)
    assert 0.0 <= s <= 1.0

def test_scope_zero():
    assert compute_scope(0, 0, 0) == 0.0


# ── escalation ────────────────────────────────────────────────────────────────

def test_override_escalation():
    escalate, etype = check_escalation(2, 0, False, 0.90)
    assert escalate is True
    assert etype == "override"

def test_normal_escalation():
    escalate, etype = check_escalation(5, 8, True, 0.5)
    assert escalate is True
    assert etype == "normal"

def test_no_escalation_diversity_fails():
    escalate, _ = check_escalation(5, 8, False, 0.5)
    assert escalate is False

def test_no_escalation_insufficient_signals():
    escalate, _ = check_escalation(3, 5, True, 0.5)
    assert escalate is False

def test_override_threshold_boundary():
    # Exactly at threshold
    escalate, etype = check_escalation(2, 0, False, 0.85)
    assert escalate is True and etype == "override"
    # Just below
    escalate2, _ = check_escalation(2, 0, False, 0.84)
    assert escalate2 is False


# ── trust ─────────────────────────────────────────────────────────────────────

def test_trust_valid_participation():
    new_t = update_trust_score(1.0, "valid_participation")
    assert new_t == pytest.approx(1.05)

def test_trust_correct_feedback():
    new_t = update_trust_score(1.0, "correct_feedback")
    assert new_t == pytest.approx(1.10)

def test_trust_bad_behavior():
    new_t = update_trust_score(1.0, "bad_behavior")
    assert new_t == pytest.approx(0.90)

def test_trust_floor():
    new_t = update_trust_score(0.2, "bad_behavior")
    assert new_t >= 0.2  # clamped at min

def test_trust_ceiling():
    new_t = update_trust_score(2.0, "valid_participation")
    assert new_t <= 2.0  # clamped at max

def test_trust_daily_decay():
    new_t = update_trust_score(1.0, "daily_decay")
    assert new_t == pytest.approx(0.995)

def test_avg_trust_empty():
    assert compute_average_trust_weight([]) == 1.0

def test_avg_trust_values():
    assert compute_average_trust_weight([1.0, 2.0]) == pytest.approx(1.5)
