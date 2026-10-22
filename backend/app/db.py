from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.schema_compat import install_live_schema_guard

engine=create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal=async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
install_live_schema_guard()

async def get_db():
    async with SessionLocal() as db: yield db
