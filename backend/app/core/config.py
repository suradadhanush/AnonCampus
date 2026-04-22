"""
Config — with mandatory startup env validation
Asserts DATABASE_URL, REDIS_URL, SECRET_KEY at import time in production.
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://anoncampus:anoncampus123@localhost:5432/anoncampus"
    SYNC_DATABASE_URL: str = "postgresql://anoncampus:anoncampus123@localhost:5432/anoncampus"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-this-in-production-must-be-at-least-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15       # 15 min access tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Scoring weights
    SCORE_WEIGHT_REPORTS: float = 0.35
    SCORE_WEIGHT_SUPPORTS: float = 0.20
    SCORE_WEIGHT_CONTEXT: float = 0.10
    SCORE_WEIGHT_DIVERSITY: float = 0.15
    SCORE_WEIGHT_SEVERITY: float = 0.20

    # Governance thresholds
    ESCALATION_MIN_REPORTS: int = 5
    ESCALATION_MIN_SUPPORTS: int = 8
    OVERRIDE_SEVERITY_THRESHOLD: float = 0.85
    OVERRIDE_MIN_REPORTS: int = 2

    # Diversity
    DIVERSITY_MIN_DEPARTMENTS: int = 2
    DIVERSITY_MIN_YEARS: int = 2
    DIVERSITY_MAX_GROUP_PERCENT: float = 0.60

    # Clustering
    CLUSTER_SAME_THRESHOLD: float = 0.82
    CLUSTER_CONDITIONAL_THRESHOLD: float = 0.75

    # Ranking
    RANK_CONFIDENCE_WEIGHT: float = 0.40
    RANK_SEVERITY_WEIGHT: float = 0.25
    RANK_RECENCY_WEIGHT: float = 0.20
    RANK_SCOPE_WEIGHT: float = 0.15
    RANK_RECENCY_DECAY: float = 0.05

    # Trust score
    TRUST_INITIAL: float = 1.0
    TRUST_MIN: float = 0.2
    TRUST_MAX: float = 2.0
    TRUST_VALID_PARTICIPATION: float = 0.05
    TRUST_CORRECT_FEEDBACK: float = 0.10
    TRUST_BAD_BEHAVIOR: float = -0.10
    TRUST_DAILY_DECAY: float = 0.995

    # Spike detection
    SPIKE_INTERACTIONS: int = 12
    SPIKE_WINDOW_MINUTES: int = 10

    # Score debounce: 1 recompute per N seconds per cluster
    SCORE_DEBOUNCE_SECONDS: int = 2

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    # Startup env validation — fail fast in production
    if s.ENVIRONMENT == "production":
        assert s.DATABASE_URL and not s.DATABASE_URL.startswith("postgresql+asyncpg://anoncampus:anoncampus123"), \
            "DATABASE_URL must be overridden in production"
        assert s.REDIS_URL and s.REDIS_URL != "redis://localhost:6379/0", \
            "REDIS_URL must be overridden in production"
        assert len(s.SECRET_KEY) >= 32 and s.SECRET_KEY != "change-this-in-production-must-be-at-least-32-chars", \
            "SECRET_KEY must be a strong random value in production"
    return s


settings = get_settings()
