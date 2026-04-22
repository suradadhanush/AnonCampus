"""
Celery tasks for cluster maintenance
"""
from app.tasks.celery_app import celery_app
from datetime import datetime, timezone, timedelta


@celery_app.task(bind=True, max_retries=2)
def daily_recluster(self):
    """
    Daily re-clustering task:
    - Re-embed any unembedded issues
    - Merge very similar clusters (cosine > 0.90)
    - Split clusters with conflicting categories
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        from app.models.cluster import Cluster
        from app.models.issue import Issue
        from app.services.clustering import get_embedding, cosine_similarity_score, update_centroid

        engine = create_engine(settings.SYNC_DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()

        try:
            # Re-embed issues without embeddings
            unembedded = db.query(Issue).filter(Issue.embedding.is_(None)).limit(100).all()
            for issue in unembedded:
                embedding = get_embedding(f"{issue.title} {issue.body}")
                if embedding:
                    issue.embedding = embedding
            db.commit()

            # Check for clusters that can be merged (same institution, same category)
            from sqlalchemy import text
            institutions = db.execute(text("SELECT DISTINCT institution_id FROM clusters WHERE status != 'ARCHIVED'")).fetchall()
            
            for (inst_id,) in institutions:
                clusters = db.query(Cluster).filter(
                    Cluster.institution_id == inst_id,
                    Cluster.status.notin_(["ARCHIVED"]),
                    Cluster.centroid_embedding.isnot(None)
                ).all()

                # Pairwise similarity check for potential merges
                merged = set()
                for i, c1 in enumerate(clusters):
                    if c1.id in merged:
                        continue
                    for j, c2 in enumerate(clusters[i+1:], i+1):
                        if c2.id in merged:
                            continue
                        if c1.category != c2.category:
                            continue
                        if c1.centroid_embedding and c2.centroid_embedding:
                            sim = cosine_similarity_score(c1.centroid_embedding, c2.centroid_embedding)
                            if sim >= 0.92:  # Very high similarity → merge
                                # Merge c2 into c1
                                db.query(Issue).filter(Issue.cluster_id == c2.id).update(
                                    {"cluster_id": c1.id}
                                )
                                c2.status = "ARCHIVED"
                                # Update centroid
                                total = c1.report_count + c2.report_count
                                if total > 0 and c2.centroid_embedding:
                                    c1.centroid_embedding = update_centroid(
                                        c1.centroid_embedding, c2.centroid_embedding, total
                                    )
                                merged.add(c2.id)

            db.commit()

        finally:
            db.close()
            engine.dispose()

    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2)
def check_dormant_clusters(self):
    """
    Mark clusters as DORMANT if no activity in 7 days
    Mark DORMANT clusters as ARCHIVED if no activity in 30 days
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        from app.models.cluster import Cluster

        engine = create_engine(settings.SYNC_DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()

        try:
            now = datetime.now(timezone.utc)
            seven_days_ago = now - timedelta(days=7)
            thirty_days_ago = now - timedelta(days=30)

            # ACTIVE → DORMANT: no activity in 7 days
            active_stale = db.query(Cluster).filter(
                Cluster.status == "ACTIVE",
                Cluster.last_activity_at < seven_days_ago
            ).all()
            for c in active_stale:
                c.status = "DORMANT"

            # DORMANT → ARCHIVED: no activity in 30 days
            dormant_old = db.query(Cluster).filter(
                Cluster.status == "DORMANT",
                Cluster.last_activity_at < thirty_days_ago
            ).all()
            for c in dormant_old:
                c.status = "ARCHIVED"

            db.commit()

        finally:
            db.close()
            engine.dispose()

    except Exception as exc:
        raise self.retry(exc=exc)
