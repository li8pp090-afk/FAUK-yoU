import os
import asyncio

import redis.asyncio as redis
from aiogram import Bot, Dispatcher

import Reply
import bUTToN

from sUM import App


def get_takeoff_ids():
    value = os.environ.get(
        "boT_TAkeoFF",
        ""
    )

    return [
        int(user_id.strip())
        for user_id in value.split("/")
        if user_id.strip().isdigit()
    ]


async def send_takeoff_message(
    bot,
    takeoff_ids
):
    if not takeoff_ids:
        return

    for user_id in takeoff_ids:
        try:
            keyboard = bUTToN.takeoff_keyboard(
                takeoff_ids
            )

            await bot.send_message(
                user_id,
                Reply.TAKEOFF_MESSAGE,
                reply_markup=keyboard
            )
        except Exception:
            pass


async def main():
    bot = Bot(
        os.environ["BOT_TOKEN"]
    )

    dp = Dispatcher()

    db = redis.from_url(
        os.environ.get(
            "REDIS_URL",
            "redis://localhost:6379/0"
        ),
        decode_responses=True
    )

    takeoff_ids = get_takeoff_ids()

    app = App(
        bot,
        dp,
        db,
        takeoff_ids
    )

    app.register()

    await app.cleanup_queues()
    await app.cleanup_files()

    await send_takeoff_message(
        bot,
        takeoff_ids
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())