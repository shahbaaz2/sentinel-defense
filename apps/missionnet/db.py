from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from apps.missionnet.config import settings

# NullPool: opens a fresh connection per checkout instead of reusing one bound to whichever event
# loop first created it. Without this, pytest-asyncio's per-test event loops fight over pooled
# asyncpg connections created on a different (already-closed) loop. Fine for this prototype's scale.
engine = create_async_engine(settings.database_url, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
