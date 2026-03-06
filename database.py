from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import config

engine = create_async_engine(
    config.DATABASE_URL,
    connect_args={"prepared_statement_cache_size": 0, "statement_cache_size": 0}
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS favorites (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                coin_id TEXT NOT NULL,
                ticker TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, coin_id)
            );
        """))
    print("БД готова.")

async def is_favorite(user_id: int, coin_id: str):
    async with async_session() as session:
        query = text("SELECT 1 FROM favorites WHERE user_id = :u AND coin_id = :c")
        result = await session.execute(query, {"u": user_id, "c": coin_id})
        return result.fetchone() is not None

async def add_favorite(user_id: int, coin_id: str, ticker: str = None):
    async with async_session() as session:
        async with session.begin():
            query = text("""
                INSERT INTO favorites (user_id, coin_id, ticker) 
                VALUES (:u, :c, :t) ON CONFLICT (user_id, coin_id) DO UPDATE SET ticker = EXCLUDED.ticker
            """)
            await session.execute(query, {"u": user_id, "c": coin_id, "t": ticker.upper() if ticker else coin_id.upper()})

async def get_favorites(user_id: int):
    async with async_session() as session:
        # Получаем данные как список словарей — это исключит ошибки распаковки
        query = text("SELECT coin_id, ticker FROM favorites WHERE user_id = :u ORDER BY created_at DESC")
        result = await session.execute(query, {"u": user_id})
        return [{"coin_id": row[0], "ticker": row[1]} for row in result.fetchall()]

async def remove_favorite(user_id: int, coin_id: str):
    async with async_session() as session:
        async with session.begin():
            query = text("DELETE FROM favorites WHERE user_id = :u AND coin_id = :c")
            await session.execute(query, {"u": user_id, "c": coin_id})
