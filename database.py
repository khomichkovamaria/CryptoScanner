from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, BigInteger
import config

Base = declarative_base()

# Подключаемся к Supabase через URL из конфига
engine = create_async_engine(config.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class User(Base):
    """Таблица пользователей (создастся сама)"""
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)

async def init_db():
    """Эта функция 'будит' базу при старте бота"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
