"""
Kết nối cơ sở dữ liệu SQLite - sử dụng SQLAlchemy async với aiosqlite.
"""
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class cho tất cả ORM models."""
    pass


# Tạo async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(connection, _record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create the schema and apply the small v2 compatibility migration."""
    from app.models import account, task_config, execution_log, system_setting  # noqa: F401
    from app.models.account import Account
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # v2 supports delegated OAuth only. Keeping the column lets an existing v1
    # SQLite database upgrade in place without a destructive table migration.
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Account).where(Account.auth_mode != "delegated").values(auth_mode="delegated")
        )
        await session.commit()


async def get_db() -> AsyncSession:
    """
    Dependency FastAPI để inject DB session vào route handlers.
    Tự động đóng session sau khi request hoàn thành.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
