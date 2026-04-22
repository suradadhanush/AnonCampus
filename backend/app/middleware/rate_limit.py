"""
Redis sliding-window rate limiter — hardened

Key format standard: rate:{user_id_or_ip}:{action}
All keys follow this exact pattern — no variations.

Limits:
  issue_submit  → 3/day     per user_id
  support       → 3/day     per user_id
  feedback      → 5/day     per user_id
  login         → 10/15min  per IP  (lockout handled in security.py)
  register      → 5/hour    per IP

Lockout: login exceeded → 15-min hard block (see security.check_login_lockout)
Fail-open: if Redis unreachable, request passes through (logged as warning)
"""
import time
import logging
from typing import Optional
from fastapi import Request, HTTPException, status
import redis as redis_sync

from app.core.config import settings

logger = logging.getLogger("anoncampus.ratelimit")

# ── Canonical key builder ─────────────────────────────────────────────────────

def _make_key(identifier: str, action: str) -> str:
    """Single canonical format: rate:{identifier}:{action}"""
    return f"rate:{identifier}:{action}"


# ── Core sliding window ───────────────────────────────────────────────────────

def _get_redis() -> redis_sync.Redis:
    return redis_sync.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1)


def _sliding_window(
    r: redis_sync.Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int, int]:
    """
    Atomic sliding window using Redis sorted set.
    Returns (allowed, current_count, retry_after_seconds).
    Score = timestamp, member = str(timestamp) [unique via microseconds].
    """
    now = time.time()
    window_start = now - window_seconds
    member = f"{now:.6f}"  # microsecond precision avoids collisions

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, "-inf", window_start)      # prune old entries
    pipe.zadd(key, {member: now})                          # add current request
    pipe.zcard(key)                                        # count in window
    pipe.expire(key, window_seconds + 1)                  # auto-cleanup TTL
    results = pipe.execute()

    count = results[2]
    allowed = count <= limit
    retry_after = int(window_seconds) if not allowed else 0
    return allowed, count, retry_after


def _enforce(identifier: str, action: str, limit: int, window: int) -> None:
    """Enforce rate limit. Raises 429 if exceeded. Fails open on Redis error."""
    key = _make_key(identifier, action)
    try:
        r = _get_redis()
        allowed, count, retry_after = _sliding_window(r, key, limit, window)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "action": action,
                    "limit": limit,
                    "window_seconds": window,
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Rate limit check failed (fail-open): {e}")


# ── Action-specific enforcers ─────────────────────────────────────────────────

def check_issue_submit_limit(user_id: int) -> None:
    _enforce(str(user_id), "issue_submit", limit=3, window=86400)


def check_support_limit(user_id: int) -> None:
    _enforce(str(user_id), "support", limit=3, window=86400)


def check_feedback_limit(user_id: int) -> None:
    _enforce(str(user_id), "feedback", limit=5, window=86400)


def check_register_limit(ip: str) -> None:
    _enforce(ip, "register", limit=5, window=3600)


# ── Idempotency ───────────────────────────────────────────────────────────────

def get_idempotency_key(request: Request) -> Optional[str]:
    """Extract Idempotency-Key header"""
    return request.headers.get("Idempotency-Key")


async def check_idempotency(db, key: str, user_id: int, endpoint: str) -> Optional[dict]:
    """Return cached response if key was already processed; else None."""
    from app.models.report import IdempotencyKey
    from sqlalchemy import select
    from datetime import timezone

    result = await db.execute(
        select(IdempotencyKey).where(IdempotencyKey.key == key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key belongs to a different user",
            )
        return existing.response_body

    return None


async def store_idempotency(
    db,
    key: str,
    user_id: int,
    endpoint: str,
    response_status: int,
    response_body: dict,
) -> None:
    from app.models.report import IdempotencyKey
    from datetime import datetime, timezone, timedelta

    record = IdempotencyKey(
        key=key,
        user_id=user_id,
        endpoint=endpoint,
        response_status=response_status,
        response_body=response_body,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(record)
    # Caller commits
