"""
db/database.py
SQLAlchemy setup — MySQL (migration_db)
19 data tables — migration warehouse
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import event, create_engine
from config import settings

from sqlalchemy.pool import AsyncAdaptedQueuePool

# Async engine (primary)
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False, 
    pool_pre_ping=True, 
    pool_recycle=3600,
    pool_size=20,
    max_overflow=10
)

# Sync engine (for conversation history and other sync endpoints)
# Convert async URL to sync URL for mysql
sync_db_url = settings.DATABASE_URL
if "mysql+aiomysql" in sync_db_url:
    sync_db_url = sync_db_url.replace("mysql+aiomysql", "mysql+pymysql")
sync_engine = create_engine(sync_db_url, echo=False, pool_pre_ping=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
SessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
