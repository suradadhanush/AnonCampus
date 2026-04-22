"""
Unit tests — moderation pipeline
"""
import pytest
from app.services.moderation import moderate_text


def test_clean_text_passes():
    is_clean, flags, title, body = moderate_text(
        "WiFi is broken in lab block C",
        "The internet connection in Computer Lab 3 has been down for a week. "
        "Students cannot complete assignments. This needs urgent attention."
    )
    assert is_clean is True
    assert flags == []


def test_email_redacted():
    _, flags, _, body = moderate_text(
        "Issue with email",
        "Please contact student@college.edu for details about this ongoing problem with the facility."
    )
    assert "pii:email" in flags
    assert "student@college.edu" not in body
    assert "[EMAIL REDACTED]" in body


def test_phone_redacted():
    _, flags, _, body = moderate_text(
        "Contact number issue",
        "The person at 9876543210 is responsible for this facility problem we all face."
    )
    assert "pii:phone" in flags
    assert "9876543210" not in body


def test_student_id_NOT_blocked():
    """Student IDs like CS21B123 must NEVER be flagged or blocked"""
    is_clean, flags, title, body = moderate_text(
        "Issue reported by CS21B123 batch students",
        "All students with roll numbers 25NU1A4430 through 25NU1A4450 are facing "
        "this infrastructure problem in ECE lab block. Needs immediate resolution."
    )
    # Should be clean — student IDs are NOT PII in this context
    assert is_clean is True
    assert "pii:id_number" not in flags
    # Student IDs should remain in text
    assert "25NU1A4430" in body


def test_direct_name_accusation_redacted():
    _, flags, _, body = moderate_text(
        "Professor accused of misconduct",
        "Professor John Smith has been unfair in grading. This is a serious issue."
    )
    assert "accusation:name_detected" in flags
    assert "John Smith" not in body


def test_too_short_blocked():
    is_clean, flags, _, _ = moderate_text("Short", "Too short")
    assert is_clean is False
    assert "too_short" in flags or "title_too_short" in flags


def test_too_long_truncated():
    long_body = "x" * 6000
    is_clean, flags, _, body = moderate_text("Valid title here that is long enough", long_body)
    assert "too_long" in flags
    assert len(body) <= 5000


def test_html_stripped():
    _, _, _, body = moderate_text(
        "Issue with portal",
        "The <script>alert('xss')</script> portal login page is broken for all students in the hostel."
    )
    assert "<script>" not in body
    assert "alert" not in body


def test_clean_grievance_with_alphanumeric():
    """Real-world: roll numbers and batch codes should never be blocked"""
    is_clean, flags, title, body = moderate_text(
        "Lab issue affecting ECE2022 batch",
        "The 2022 batch students (roll 22NU1A0401 to 22NU1A0460) cannot access "
        "the server room. Equipment tagged LAB-CSE-003 is broken since Monday."
    )
    assert is_clean is True
    # Equipment tags and roll numbers preserved
    assert "LAB-CSE-003" in body
