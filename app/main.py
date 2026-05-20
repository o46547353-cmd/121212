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
async def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN is missing in .env")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is missing in .env")

    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # DB Init
    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
