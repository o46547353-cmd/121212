import asyncio
import os
import logging
from typing import Callable, Dict, Any, Awaitable
from pathlib import Path
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

from app.db.models import Base
from app.bot.handlers import router

load_dotenv()

logging.basicConfig(level=logging.INFO)

# --- Database Middleware ---
class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data["session"] = session
            return await handler(event, data)

# --- Main setup ---
async def init_db(engine):
    # Retry logic: up to 10 retries, waiting 3 seconds each (total 30s)
    retries = 10
    for i in range(retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logging.info("Database initialized successfully.")
            return True
        except Exception as e:
            logging.error(f"Database connection failed (attempt {i+1}/{retries}): {e}")
            await asyncio.sleep(3)
    return False

async def main():
    logging.info("Попытка загрузки токена из переменных окружения...")
    bot_token = os.getenv("API_TOKEN")
    if not bot_token:
        logging.error("Ошибка: токен не найден в переменной API_TOKEN")
        return

    masked_token = f"{bot_token[:5]}...{bot_token[-5:]}" if len(bot_token) > 10 else "***"
    logging.info(f"Токен загружен: {masked_token}")

    # Set up Bothost persistent database directory
    data_dir = Path("/app/data")
    data_dir.mkdir(parents=True, exist_ok=True)

    default_db_url = f"sqlite+aiosqlite:///{data_dir}/bot_database.db"
    db_url = os.getenv("DATABASE_URL", default_db_url)

    logging.info(f"Подключение к БД по адресу: {db_url}")

    # DB Init
    engine = create_async_engine(db_url, echo=False)

    success = await init_db(engine)
    if not success:
        logging.error("Could not connect to the database after multiple retries. Exiting.")
        return

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Bot & Dispatcher Init
    bot = Bot(token=bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middlewares & Routers
    dp.update.middleware(DbSessionMiddleware(session_pool=session_maker))
    dp.include_router(router)

    # Start Polling
    logging.info("Starting bot via long polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
