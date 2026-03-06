import os

# Токены из переменных окружения Render
API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

# Если БД подключена, добавляем спец-префикс для асинхронности
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

PORT = int(os.getenv("PORT", 8080))
