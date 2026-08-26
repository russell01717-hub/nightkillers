"""
Night Killers — Mafia Bot v5.0
Entry point: run this script to start the bot.
"""

import asyncio
import logging
import os
import sys
import signal

try:
    sys.path.insert(0, r"D:\pylibs")
except Exception:
    pass

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import ErrorEvent

from mafia_bot.config import TOKEN
from mafia_bot.db import init_db, load_active_games, delete_active_game
from mafia_bot.models import games
from mafia_bot.game_engine import continue_game

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("MafiaBot")


async def global_error_handler(event: ErrorEvent):
    log.error(f"Global error: {event.exception}", exc_info=event.exception)
    try:
        if event.update.message:
            await event.update.message.answer(
                "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
            )
    except Exception:
        pass


async def on_shutdown(bot: Bot):
    log.info("Shutting down...")
    for chat_id, game in list(games.items()):
        from mafia_bot.db import save_active_game
        try:
            save_active_game(game)
        except Exception:
            pass


async def main():
    log.info("Starting Night Killers v5.0...")

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher()

    dp.errors.register(global_error_handler)

    from mafia_bot.handlers.commands import register as register_commands
    from mafia_bot.handlers.callbacks import register as register_callbacks
    from mafia_bot.handlers.payments import router as payments_router

    register_commands(dp, bot)
    register_callbacks(dp, bot)
    dp.include_router(payments_router)

    init_db()

    # Restore active games
    restored = load_active_games()
    for chat_id, game in restored.items():
        games[chat_id] = game
        log.info(f"Restored game in chat {chat_id} (phase: {game.phase.value}, day: {game.day})")

    dp.startup.register(lambda: log.info("Bot started!"))
    dp.shutdown.register(on_shutdown)

    # Resume any active games
    for chat_id, game in list(games.items()):
        await continue_game(bot, chat_id)

    log.info("Bot is running. Press Ctrl+C to stop.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
    except SystemExit:
        pass
