from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import config

engine = create_async_engine(
    config.DATABASE_URL,
    connect_args={
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0
    }
)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        print("База данных успешно подключена!")
