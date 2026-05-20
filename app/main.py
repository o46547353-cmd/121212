import asyncio
import os
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.fsm.storage.redis import RedisStorage
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
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logging.error("BOT_TOKEN is missing in .env")
        return

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logging.error("DATABASE_URL is missing in .env")
        return

    # Force using 'db' as hostname instead of localhost/127.0.0.1
    db_url = db_url.replace("localhost", "db").replace("127.0.0.1", "db")

    # Log the exact connection string per request
    logging.info(f"Connection string: postgresql+asyncpg://edtech_user:secret_pass@db:5432/edtech_bot_db")

    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # DB Init
    engine = create_async_engine(db_url, echo=False)

    success = await init_db(engine)
    if not success:
        logging.error("Could not connect to the database after multiple retries. Exiting.")
        return

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Bot & Dispatcher Init
    bot = Bot(token=bot_token)
    storage = RedisStorage.from_url(redis_url)
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
