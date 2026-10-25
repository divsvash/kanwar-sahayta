"""
Async SQLAlchemy 2.0 database configuration.

Driver-aware: the demo runs on SQLite (zero infra), while the original
MySQL docker-compose path still works by setting DATABASE_URL.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

DATABASE_URL = settings.DATABASE_URL
IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_async_engine(DATABASE_URL, echo=settings.DEBUG)
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,
        connect_args={"charset": "utf8mb4", "use_unicode": True},
    )
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def set_mysql_session_vars(dbapi_connection, connection_record):
        """Set MySQL session variables on each connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("SET SESSION time_zone = '+05:30'")  # IST
        cursor.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES'")
        cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
