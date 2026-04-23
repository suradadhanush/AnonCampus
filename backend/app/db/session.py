from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import ssl


def _clean_db_url(url: str) -> str:
    """Remove all query parameters from asyncpg URL — SSL handled via connect_args"""
    return url.split('?')[0]


_ssl_ctx = ssl.create_default_context()

engine = create_async_engine(
    _clean_db_url(settings.DATABASE_URL),
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"ssl": _ssl_ctx},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        from app.models import user, cluster, issue, report
        await conn.run_sync(Base.metadata.create_all)
