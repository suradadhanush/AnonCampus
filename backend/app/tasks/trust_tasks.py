"""
Daily trust score decay task
"""
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2)
def apply_trust_decay(self):
    """Apply daily trust decay: T = T * 0.995 for all users"""
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings

        engine = create_engine(settings.SYNC_DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()

        try:
            db.execute(text(f"""
                UPDATE users 
                SET trust_score = GREATEST(:min_trust, trust_score * :decay)
                WHERE is_active = true
            """), {
                "min_trust": settings.TRUST_MIN,
                "decay": settings.TRUST_DAILY_DECAY
            })
            db.commit()
        finally:
            db.close()
            engine.dispose()

    except Exception as exc:
        raise self.retry(exc=exc)
