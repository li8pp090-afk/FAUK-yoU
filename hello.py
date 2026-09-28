import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ChatType
from aiogram.types import Message

import CAsh
import LoGic
import Order
import Reply
import bToN


TOKEN = Order.get_bot_token()

bot = Bot(TOKEN)
dp = Dispatcher()

dp.include_router(bToN.router)


async def send_startup_message():
    for user_id in Order.get_startup_ids():
        try:
            await bot.send_message(
                chat_id=int(user_id),
                text=Reply.STARTUP_REPLY,
                reply_markup=bToN.get_markup()
            )
        except Exception:
            pass


@dp.message(
    lambda message:
    message.chat.type == ChatType.PRIVATE
)
async def message_handler(message: Message):
    await LoGic.message_handler(
        bot,
        message
    )


async def main():
    await CAsh.init_db()
    await CAsh.recover_stale_tasks()

    try:
        await bot.delete_webhook(
            drop_pending_updates=True
        )

        await send_startup_message()

        await dp.start_polling(
            bot
        )

    finally:
        await CAsh.close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())