"""
Observability module — hardened

- StudentIDMaskingFilter: masks all tokens matching student ID pattern in logs
- StructuredFormatter: JSON log output
- log_event: async DB event log helper using EventType enum (no free text)
- Metric helpers: score_computed, sla_breach, spike_detected, escalation
"""
import json
import logging
import re
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional

from app.models.report import EventType

# ── Student ID masking filter ─────────────────────────────────────────────────

# Matches uppercase alphanumeric 5-15 chars (student ID pattern)
_STUDENT_ID_RE = re.compile(r'\b[A-Z0-9]{5,15}\b')


class StudentIDMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _STUDENT_ID_RE.sub(
                lambda m: "****" + m.group()[-4:] if len(m.group()) > 4 else "****",
                record.msg,
            )
        if record.args and isinstance(record.args, dict):
            for k, v in record.args.items():
                if isinstance(v, str):
                    record.args[k] = _STUDENT_ID_RE.sub("****", v)
        return True


# ── JSON formatter ────────────────────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "fn": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "extra"):
            entry.update(record.extra)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure structured JSON logging.
    level=logging.WARNING in production, logging.INFO in development.
    student_id tokens are masked in all log records.
    """
    root = logging.getLogger("anoncampus")
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        handler.addFilter(StudentIDMaskingFilter())
        root.addHandler(handler)
    # Always suppress noisy third-party libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)
    return root


logger = logging.getLogger("anoncampus.obs")


# ── DB event logging ──────────────────────────────────────────────────────────

async def log_event(
    db,
    institution_id: int,
    event_type: EventType,               # ENUM — no free text
    cluster_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Append event to event_log. Caller must commit."""
    from app.models.report import EventLog
    event = EventLog(
        institution_id=institution_id,
        cluster_id=cluster_id,
        actor_id=actor_id,
        event_type=event_type,
        payload=payload or {},
    )
    db.add(event)


# ── Metric log helpers ────────────────────────────────────────────────────────

def log_score_computed(cluster_id: int, confidence: float, escalated: bool) -> None:
    logger.info("score_computed", extra={
        "event": "score_computed",
        "cluster_id": cluster_id,
        "confidence": round(confidence, 4),
        "escalated": escalated,
    })


def log_sla_breach(cluster_id: int, institution_id: int, deadline: str) -> None:
    logger.warning("sla_breach", extra={
        "event": "sla_breach",
        "cluster_id": cluster_id,
        "institution_id": institution_id,
        "deadline": deadline,
        "alert": True,
    })


def log_spike_detected(cluster_id: int, count: int) -> None:
    logger.warning("spike_detected", extra={
        "event": "spike_detected",
        "cluster_id": cluster_id,
        "interaction_count": count,
        "alert": True,
    })


def log_escalation(cluster_id: int, escalation_type: str) -> None:
    logger.info("escalation_triggered", extra={
        "event": "escalation_triggered",
        "cluster_id": cluster_id,
        "escalation_type": escalation_type,
    })


# ── Timing decorator ──────────────────────────────────────────────────────────

def timed(label: str):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                logger.debug(f"{label} ok in {(time.monotonic()-start)*1000:.1f}ms")
                return result
            except Exception as e:
                logger.error(f"{label} failed after {(time.monotonic()-start)*1000:.1f}ms: {e}")
                raise
        return wrapper
    return decorator
