import os

API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Просто меняем протокол на асинхронный
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

PORT = int(os.getenv("PORT", 8080))
