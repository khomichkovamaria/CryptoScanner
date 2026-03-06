import os

API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # 1. Обеспечиваем асинхронный префикс
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # 2. Очищаем старые параметры, если они есть
    if "?" in DATABASE_URL:
        base_url = DATABASE_URL.split("?")[0]
    else:
        base_url = DATABASE_URL

    # 3. Принудительно добавляем параметры для работы через PgBouncer (Supabase)
    # statement_cache_size=0 — это то, что требует ошибка в логах
    DATABASE_URL = f"{base_url}?prepared_statement_cache_size=0&statement_cache_size=0"

PORT = int(os.getenv("PORT", 8080))
