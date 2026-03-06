import os

# Токены из переменных окружения Render
API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # 1. Заменяем префикс на асинхронный
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # 2. Удаляем параметры pgbouncer, которые вызывают ошибку TypeError
    if "?pgbouncer=true" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("?pgbouncer=true", "")
    elif "&pgbouncer=true" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("&pgbouncer=true", "")

PORT = int(os.getenv("PORT", 8080))
