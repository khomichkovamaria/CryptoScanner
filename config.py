import os

API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # 1. Исправляем протокол на асинхронный
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # 2. Полностью очищаем URL от старых параметров (всего, что после ?)
    base_url = DATABASE_URL.split("?")[0]

    # 3. Добавляем параметры, которые ГАРАНТИРОВАННО отключают кэш запросов
    # Это решает проблему "prepared statement already exists"
    DATABASE_URL = f"{base_url}?prepared_statement_cache_size=0&statement_cache_size=0"

PORT = int(os.getenv("PORT", 8080))
