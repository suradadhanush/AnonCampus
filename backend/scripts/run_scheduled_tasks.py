"""
Standalone scheduled tasks script — runs without Celery or Redis.
Used by Render Cron Job (or any cron runner) to execute daily maintenance.

Why this exists:
  Celery tasks use @celery_app.task(bind=True) which requires a running
  Celery worker and broker. On free hosting those aren't reliably available
  on a schedule. This script extracts the same DB logic and runs it
  directly via SQLAlchemy — only needs DATABASE_URL in the environment.

Usage:
  python scripts/run_scheduled_tasks.py

Tasks:
  1. Trust score decay         — T = T * 0.995 for all active users
  2. Dormant cluster check     — ACTIVE->DORMANT (7d), DORMANT->ARCHIVED (30d)
  3. Idempotency key cleanup   — DELETE WHERE expires_at < NOW()
  4. Refresh token cleanup     — DELETE WHERE expires_at < NOW()
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta

# Put backend/ on path so app.core.config resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scheduled_tasks")


def get_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    engine = create_engine(
        settings.SYNC_DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )
    Session = sessionmaker(bind=engine)
    return Session(), engine


def run_trust_decay():
    from sqlalchemy import text
    from app.core.config import settings
    db, engine = get_db()
    try:
        r = db.execute(
            text("""
                UPDATE users
                SET trust_score = GREATEST(:min_trust, trust_score * :decay)
                WHERE is_active = true
            """),
            {"min_trust": settings.TRUST_MIN, "decay": settings.TRUST_DAILY_DECAY},
        )
        db.commit()
        log.info("Trust decay done — %d users updated", r.rowcount)
    except Exception as e:
        db.rollback()
        log.error("Trust decay failed: %s", e)
        raise
    finally:
        db.close()
        engine.dispose()


def run_dormant_check():
    from sqlalchemy import text
    db, engine = get_db()
    try:
        now = datetime.now(timezone.utc)
        seven_days  = (now - timedelta(days=7)).isoformat()
        thirty_days = (now - timedelta(days=30)).isoformat()

        r1 = db.execute(
            text("""
                UPDATE clusters SET status = 'dormant', updated_at = NOW()
                WHERE status = 'active' AND last_activity_at < :cutoff
            """),
            {"cutoff": seven_days},
        )
        r2 = db.execute(
            text("""
                UPDATE clusters SET status = 'archived', updated_at = NOW()
                WHERE status = 'dormant' AND last_activity_at < :cutoff
            """),
            {"cutoff": thirty_days},
        )
        db.commit()
        log.info("Dormant check — %d->dormant, %d->archived", r1.rowcount, r2.rowcount)
    except Exception as e:
        db.rollback()
        log.error("Dormant check failed: %s", e)
        raise
    finally:
        db.close()
        engine.dispose()


def run_idempotency_cleanup():
    from sqlalchemy import text
    db, engine = get_db()
    try:
        r = db.execute(text("DELETE FROM idempotency_keys WHERE expires_at < NOW()"))
        db.commit()
        log.info("Idempotency cleanup — %d rows deleted", r.rowcount)
    except Exception as e:
        db.rollback()
        log.error("Idempotency cleanup failed: %s", e)
        raise
    finally:
        db.close()
        engine.dispose()


def run_refresh_token_cleanup():
    from sqlalchemy import text
    db, engine = get_db()
    try:
        r = db.execute(text("DELETE FROM refresh_tokens WHERE expires_at < NOW()"))
        db.commit()
        log.info("Refresh token cleanup — %d rows deleted", r.rowcount)
    except Exception as e:
        db.rollback()
        log.error("Refresh token cleanup failed: %s", e)
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    log.info("=== Scheduled tasks starting ===")
    errors = []

    for name, fn in [
        ("Trust decay",           run_trust_decay),
        ("Dormant cluster check", run_dormant_check),
        ("Idempotency cleanup",   run_idempotency_cleanup),
        ("Refresh token cleanup", run_refresh_token_cleanup),
    ]:
        log.info("Running: %s", name)
        try:
            fn()
        except Exception as e:
            log.error("FAILED — %s: %s", name, e)
            errors.append(name)

    if errors:
        log.error("=== Completed with errors: %s ===", ", ".join(errors))
        sys.exit(1)
    else:
        log.info("=== All tasks completed successfully ===")
        sys.exit(0)
