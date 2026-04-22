"""Initial schema with all tables and constraints

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUMs first
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE userrole AS ENUM ('student', 'admin', 'super_admin');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cluster_status_enum AS ENUM ('new','active','dormant','archived','resolved','reopened');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE issue_status_enum AS ENUM ('new','active','dormant','archived','resolved','reopened');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE signal_type_enum AS ENUM ('report','support','context');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE event_type_enum AS ENUM (
                'ISSUE_CREATED','CLUSTER_ASSIGNED','CLUSTER_CREATED',
                'SUPPORT_ADDED','CONTEXT_ADDED','SCORE_UPDATED',
                'ESCALATION_TRIGGERED','ADMIN_ACTION','FEEDBACK_SUBMITTED',
                'SPIKE_DETECTED','STATUS_TRANSITION','TRUST_UPDATED'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # institutions
    op.execute("""
        CREATE TABLE IF NOT EXISTS institutions (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            domain VARCHAR(100) NOT NULL UNIQUE,
            allowed_email_domain VARCHAR(100) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            tier VARCHAR(20) NOT NULL DEFAULT 'medium',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_institutions_domain ON institutions(domain)")

    # users
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE RESTRICT,
            anon_id VARCHAR(36) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            hashed_password VARCHAR(255) NOT NULL,
            student_id VARCHAR(50) NOT NULL,
            role userrole NOT NULL DEFAULT 'student',
            department VARCHAR(100) NOT NULL DEFAULT 'Unknown',
            academic_year INTEGER NOT NULL DEFAULT 1,
            trust_score FLOAT NOT NULL DEFAULT 1.0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_user_institution_student UNIQUE (institution_id, student_id),
            CONSTRAINT ck_user_academic_year CHECK (academic_year BETWEEN 1 AND 4),
            CONSTRAINT ck_user_trust_score CHECK (trust_score BETWEEN 0.1 AND 2.1)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_institution_id ON users(institution_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_institution_role ON users(institution_id, role)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_anon_id ON users(anon_id)")

    # clusters
    op.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            id SERIAL PRIMARY KEY,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            summary TEXT,
            category VARCHAR(100) NOT NULL DEFAULT 'general',
            status cluster_status_enum NOT NULL DEFAULT 'new',
            severity FLOAT NOT NULL DEFAULT 0.5,
            confidence_score FLOAT NOT NULL DEFAULT 0.0,
            visibility_score FLOAT NOT NULL DEFAULT 0.0,
            diversity_score FLOAT NOT NULL DEFAULT 0.0,
            diversity_valid BOOLEAN NOT NULL DEFAULT FALSE,
            is_escalated BOOLEAN NOT NULL DEFAULT FALSE,
            escalation_type VARCHAR(30),
            report_count INTEGER NOT NULL DEFAULT 0,
            support_count INTEGER NOT NULL DEFAULT 0,
            context_count INTEGER NOT NULL DEFAULT 0,
            scope FLOAT NOT NULL DEFAULT 0.0,
            centroid_embedding JSON,
            departments_involved JSON NOT NULL DEFAULT '[]',
            years_involved JSON NOT NULL DEFAULT '[]',
            sla_deadline TIMESTAMPTZ,
            sla_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            sla_breached_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            last_activity_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT ck_cluster_severity CHECK (severity BETWEEN 0.0 AND 1.0),
            CONSTRAINT ck_cluster_confidence CHECK (confidence_score BETWEEN 0.0 AND 2.5),
            CONSTRAINT ck_cluster_report_count CHECK (report_count >= 0)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_clusters_institution_status ON clusters(institution_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_clusters_institution_visibility ON clusters(institution_id, visibility_score)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_clusters_escalated ON clusters(institution_id, is_escalated)")

    # issues
    op.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id SERIAL PRIMARY KEY,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            cluster_id INTEGER REFERENCES clusters(id) ON DELETE SET NULL,
            title VARCHAR(500) NOT NULL,
            body TEXT NOT NULL,
            category VARCHAR(100) NOT NULL DEFAULT 'general',
            status issue_status_enum NOT NULL DEFAULT 'new',
            severity FLOAT NOT NULL DEFAULT 0.5,
            embedding JSON,
            is_moderated BOOLEAN NOT NULL DEFAULT FALSE,
            moderation_flags JSON NOT NULL DEFAULT '[]',
            submitter_department VARCHAR(100),
            submitter_year INTEGER,
            submitter_trust_at_submission FLOAT NOT NULL DEFAULT 1.0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT ck_issue_severity CHECK (severity BETWEEN 0.0 AND 1.0)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_issues_institution_status ON issues(institution_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_issues_institution_cluster ON issues(institution_id, cluster_id)")

    # reports
    op.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            reporter_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            signal_type signal_type_enum NOT NULL DEFAULT 'report',
            context_text TEXT,
            reporter_department VARCHAR(100),
            reporter_year INTEGER,
            reporter_trust_at_time FLOAT NOT NULL DEFAULT 1.0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_report_user_issue_type UNIQUE (reporter_id, issue_id, signal_type)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_reports_issue_type ON reports(issue_id, signal_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reports_institution ON reports(institution_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reports_reporter ON reports(reporter_id)")

    # votes
    op.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id SERIAL PRIMARY KEY,
            issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            voter_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_vote_user_issue UNIQUE (voter_id, issue_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_votes_issue ON votes(issue_id)")

    # feedback
    op.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            sentiment VARCHAR(20) NOT NULL,
            rating INTEGER,
            comment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_feedback_user_issue UNIQUE (user_id, issue_id),
            CONSTRAINT ck_feedback_sentiment CHECK (sentiment IN ('resolved','unresolved','partial')),
            CONSTRAINT ck_feedback_rating CHECK (rating IS NULL OR rating BETWEEN 1 AND 5)
        )
    """)

    # admin_actions
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_actions (
            id SERIAL PRIMARY KEY,
            cluster_id INTEGER REFERENCES clusters(id) ON DELETE SET NULL,
            admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            action_type VARCHAR(50) NOT NULL,
            old_status VARCHAR(30),
            new_status VARCHAR(30),
            reason TEXT,
            extra_meta JSON NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_admin_actions_cluster ON admin_actions(cluster_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_admin_actions_institution ON admin_actions(institution_id)")

    # event_log
    op.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id SERIAL PRIMARY KEY,
            cluster_id INTEGER REFERENCES clusters(id) ON DELETE SET NULL,
            actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            event_type event_type_enum NOT NULL,
            payload JSON NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_log_cluster ON event_log(cluster_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_log_institution_type ON event_log(institution_id, event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_log_created ON event_log(created_at)")

    # refresh_tokens
    op.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL PRIMARY KEY,
            token_hash VARCHAR(128) NOT NULL UNIQUE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            revoked BOOLEAN NOT NULL DEFAULT FALSE,
            revoked_at TIMESTAMPTZ,
            revoked_reason VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            family_id VARCHAR(36) NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user ON refresh_tokens(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires ON refresh_tokens(expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family ON refresh_tokens(family_id)")

    # idempotency_keys
    op.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            id SERIAL PRIMARY KEY,
            key VARCHAR(64) NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            endpoint VARCHAR(100) NOT NULL,
            response_status INTEGER,
            response_body JSON,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_idempotency_expires ON idempotency_keys(expires_at)")

    # system_config
    op.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            id SERIAL PRIMARY KEY,
            institution_id INTEGER REFERENCES institutions(id) ON DELETE CASCADE,
            key VARCHAR(100) NOT NULL,
            value TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_config_inst_key_base UNIQUE (institution_id, key)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sysconfig_institution ON system_config(institution_id)")
    # PARTIAL UNIQUE INDEX — only one is_active=TRUE per (institution_id, key)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uix_sysconfig_active
        ON system_config(institution_id, key)
        WHERE is_active = TRUE
    """)


def downgrade() -> None:
    tables = [
        "system_config", "idempotency_keys", "refresh_tokens",
        "event_log", "admin_actions", "feedback", "votes",
        "reports", "issues", "clusters", "users", "institutions",
    ]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")

    for enum in ["event_type_enum", "signal_type_enum", "issue_status_enum",
                 "cluster_status_enum", "userrole"]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
