import os
import asyncio

from aiogram import Bot, Dispatcher

import CAsh
import Reply
import bUTToN

from sUM import App


def get_takeoff_ids():
    return [
        int(x)
        for x in os.getenv("boT_TAkeoFF", "").split("/")
        if x.strip().isdigit()
    ]


async def main():
    bot = Bot(os.environ["BOT_TOKEN"])
    dp = Dispatcher()

    db = await CAsh.create_pool(
        os.environ["DATABASE_URL"]
    )

    await CAsh.init_db(db)

    app = App(
        bot,
        dp,
        db,
        get_takeoff_ids()
    )

    app.register()

    await app.cleanup_queues()
    await app.cleanup_files()

    for user_id in get_takeoff_ids():
        try:
            await bot.send_message(
                user_id,
                Reply.TAKEOFF_MESSAGE,
                reply_markup=bUTToN.takeoff_keyboard(
                    get_takeoff_ids()
                )
            )
        except Exception:
            pass

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())