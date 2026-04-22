"""Global test configuration"""
import pytest

# Disable Celery tasks in tests
import unittest.mock as mock
import app.services.issue_service as iss
iss._trigger_score = mock.MagicMock()
