from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import config

# Добавляем параметр statement_cache_size=0 для совместимости с PgBouncer
engine = create_async_engine(
    config.DATABASE_URL,
    echo=True,
    prepared_statement_cache_size=0  # Это решит проблему DuplicatePreparedStatementError
)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    # Здесь можно добавить создание таблиц через Base.metadata.create_all
    # Но для теста пока оставляем просто подключение
    async with engine.begin() as conn:
        print("База данных успешно подключена!")
