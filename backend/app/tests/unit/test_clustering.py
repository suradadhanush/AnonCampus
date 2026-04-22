"""
Unit tests — clustering service
"""
import pytest
from app.services.clustering import (
    cosine_score, tfidf_similarity, determine_cluster_action,
    update_centroid, classify_category, estimate_severity,
)


def test_cosine_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert cosine_score(v, v) == pytest.approx(1.0, abs=1e-5)


def test_cosine_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert cosine_score(a, b) == pytest.approx(0.0, abs=1e-5)


def test_tfidf_identical():
    score = tfidf_similarity("wifi broken lab", "wifi broken lab")
    assert score == pytest.approx(1.0, abs=1e-5)


def test_tfidf_different():
    score = tfidf_similarity("wifi broken lab", "exam results delayed")
    assert score < 0.5


def test_determine_cluster_new_when_no_candidates():
    action, cid, score = determine_cluster_action([0.1, 0.2], "test", [])
    assert action == "new"
    assert cid is None


def test_determine_cluster_same_high_similarity():
    vec = [1.0, 0.0, 0.0, 0.0]
    # Very similar vector
    similar = [0.99, 0.1, 0.0, 0.0]
    candidates = [(1, vec, "Wifi issue")]
    action, cid, score = determine_cluster_action(similar, "wifi issue", candidates)
    # Should match as same or conditional
    assert action in ("same", "conditional")
    assert cid == 1


def test_determine_cluster_new_low_similarity():
    vec = [1.0, 0.0, 0.0, 0.0]
    diff = [0.0, 0.0, 1.0, 0.0]  # orthogonal
    candidates = [(1, vec, "Wifi issue")]
    action, cid, _ = determine_cluster_action(diff, "exam problem", candidates)
    assert action == "new"
    assert cid is None


def test_update_centroid_no_current():
    result = update_centroid(None, [1.0, 0.0], 1)
    assert result == [1.0, 0.0]


def test_update_centroid_no_new():
    existing = [1.0, 0.0]
    result = update_centroid(existing, None, 5)
    assert result == existing


def test_update_centroid_normalized():
    c = [1.0, 0.0]
    n = [0.0, 1.0]
    result = update_centroid(c, n, 2)
    # Should be normalized
    import math
    magnitude = math.sqrt(sum(x**2 for x in result))
    assert abs(magnitude - 1.0) < 1e-5


def test_classify_infrastructure():
    assert classify_category("The wifi in computer lab is broken") == "infrastructure"


def test_classify_academics():
    assert classify_category("Exam results are delayed by the faculty") == "academics"


def test_classify_safety():
    assert classify_category("There is a threat of ragging in the hostel block") == "safety"


def test_classify_general_fallback():
    assert classify_category("Something is wrong here") == "general"


def test_severity_high_keywords():
    s = estimate_severity("This is urgent and dangerous harassment in campus")
    assert s >= 0.7


def test_severity_default():
    s = estimate_severity("The notice board needs updating")
    assert 0.4 <= s <= 0.6


def test_severity_bounded():
    s = estimate_severity("urgent dangerous critical emergency immediate threat abuse violence")
    assert 0.0 <= s <= 1.0
