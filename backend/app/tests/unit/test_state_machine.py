"""
Unit tests — state machine transitions
"""
import pytest
from app.models.cluster import is_valid_transition, ALLOWED_TRANSITIONS


def test_new_to_active_valid():
    assert is_valid_transition("new", "active") is True

def test_new_to_resolved_invalid():
    assert is_valid_transition("new", "resolved") is False

def test_active_to_dormant_valid():
    assert is_valid_transition("active", "dormant") is True

def test_active_to_resolved_valid():
    assert is_valid_transition("active", "resolved") is True

def test_active_to_new_invalid():
    assert is_valid_transition("active", "new") is False

def test_dormant_to_active_valid():
    assert is_valid_transition("dormant", "active") is True

def test_dormant_to_archived_valid():
    assert is_valid_transition("dormant", "archived") is True

def test_archived_has_no_transitions():
    assert ALLOWED_TRANSITIONS["archived"] == []
    assert is_valid_transition("archived", "active") is False

def test_resolved_to_reopened_valid():
    assert is_valid_transition("resolved", "reopened") is True

def test_resolved_to_active_invalid():
    assert is_valid_transition("resolved", "active") is False

def test_reopened_to_active_valid():
    assert is_valid_transition("reopened", "active") is True

def test_unknown_state_invalid():
    assert is_valid_transition("nonexistent", "active") is False

def test_all_states_have_entries():
    for state in ["new", "active", "dormant", "archived", "resolved", "reopened"]:
        assert state in ALLOWED_TRANSITIONS
