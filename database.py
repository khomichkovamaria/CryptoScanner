from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import config

# Настройка движка с параметрами для корректной работы через пулер (Supabase)
engine = create_async_engine(
    config.DATABASE_URL,
    connect_args={
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0
    }
)

# Создание фабрики сессий
async_session = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def init_db():
    """Проверка подключения и создание таблицы (если её нет)."""
    async with engine.begin() as conn:
        # Создаем таблицу избранного прямо из кода, если забыли создать в SQL Editor
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS favorites (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                coin_id TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("База данных успешно подключена и таблица проверена!")

async def add_favorite(user_id: int, coin_id: str):
    """Добавляет монету в избранное пользователя."""
    async with async_session() as session:
        async with session.begin():
            # Используем ON CONFLICT, чтобы не дублировать записи (если захотим добавить уникальность позже)
            query = text("""
                INSERT INTO favorites (user_id, coin_id) 
                VALUES (:u, :c)
            """)
            await session.execute(query, {"u": user_id, "c": coin_id})
            await session.commit()

async def get_favorites(user_id: int):
    """Получает список всех ID монет в избранном у конкретного пользователя."""
    async with async_session() as session:
        query = text("SELECT coin_id FROM favorites WHERE user_id = :u")
        result = await session.execute(query, {"u": user_id})
        # Возвращаем список строк (названий монет)
        return [row[0] for row in result.fetchall()]

async def remove_favorite(user_id: int, coin_id: str):
    """Удаляет монету из избранного."""
    async with async_session() as session:
        async with session.begin():
            query = text("DELETE FROM favorites WHERE user_id = :u AND coin_id = :c")
            await session.execute(query, {"u": user_id, "c": coin_id})
            await session.commit()
