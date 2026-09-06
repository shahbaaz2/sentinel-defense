"""Sentinel's own database engine/session.

Lives in `domain/`, not `apps/api/`, so `services/*` (event_ingestor, detection_engine,
incident_engine) can depend on it without importing from `apps/` - that would invert the intended
dependency direction (apps depends on services/domain, never the reverse).
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

SENTINEL_DATABASE_URL = os.environ.get(
    "SENTINEL_DATABASE_URL", "postgresql+asyncpg://sentinel:sentinel@127.0.0.1:5432/sentinel"
)

# NullPool for the same reason as apps/missionnet/db.py: avoids pooled asyncpg connections binding
# to a pytest-asyncio event loop that later tests can't reuse.
engine = create_async_engine(SENTINEL_DATABASE_URL, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
