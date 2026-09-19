import os
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile

from Reply import (
    TAKEOFF_MESSAGE,
    EDIT_TRIGGER,
    BOT_TRIGGER,
    EDIT_MESSAGE,
    BOT_REPLIES
)

from CAsh import (
    init_db,
    get_mode,
    save_edit_permission,
    get_next_reply
)

from bUTToN import (
    mode_keyboard,
    register_button_handlers
)

from yTFMe import (
    download_virtual,
    download_voice
)

TOKEN = os.getenv("BOT_TOKEN")
boT_TAkeoFF = os.getenv("boT_TAkeoFF")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
register_button_handlers(dp)

async def send_takeoff_notifications():
    if not boT_TAkeoFF:
        return

    chat_ids = [cid.strip() for cid in boT_TAkeoFF.split("/") if cid.strip()]

    for chat_id in chat_ids:
        try:
            await bot.send_message(
                chat_id=int(chat_id),
                text=TAKEOFF_MESSAGE
            )
        except Exception:
            pass

def get_scope_id(message: Message):
    if message.chat.type == "private":
        return f"private:{message.from_user.id}"

    return f"chat:{message.chat.id}"

def is_link(text):
    if not text:
        return False

    lowered = text.lower()

    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("www.")
        or "t.me/" in lowered
    )

async def is_authorized(message: Message):
    if message.chat.type == "private":
        return True

    member = await bot.get_chat_member(
        message.chat.id,
        message.from_user.id
    )

    return member.status in {
        "creator",
        "administrator"
    }

@dp.message(F.text == EDIT_TRIGGER)
async def edit_command(message: Message):
    if not await is_authorized(message):
        return

    scope_id = get_scope_id(message)
    current_mode = await __import__("CAsh").get_mode(scope_id)

    sent_message = await message.reply(
        EDIT_MESSAGE,
        reply_markup=mode_keyboard(current_mode)
    )

    await save_edit_permission(
        message.chat.id,
        sent_message.message_id,
        message.from_user.id
    )

@dp.message(F.text)
async def text_handler(message: Message):
    if message.text == EDIT_TRIGGER:
        return

    if is_link(message.text):
        scope_id = get_scope_id(message)
        mode = await __import__("CAsh").get_mode(scope_id)

        if mode == "voice":
            file_paths = await asyncio.to_thread(
                download_voice,
                message.text
            )

            for index in range(0, len(file_paths), 10):
                batch = file_paths[index:index + 10]

                for file_path in batch:
                    await message.reply_voice(
                        FSInputFile(file_path)
                    )
        else:
            file_paths = await asyncio.to_thread(
                download_virtual,
                message.text
            )

            for index in range(0, len(file_paths), 10):
                batch = file_paths[index:index + 10]

                for file_path in batch:
                    await message.reply_document(
                        FSInputFile(file_path)
                    )

        return

    if message.chat.type == "private":
        scope_id = get_scope_id(message)

        index = await get_next_reply(
            scope_id,
            message.from_user.id,
            len(BOT_REPLIES)
        )

        await message.reply(
            BOT_REPLIES[index]
        )
        return

    if message.text != BOT_TRIGGER:
        return

    scope_id = get_scope_id(message)

    index = await get_next_reply(
        scope_id,
        message.from_user.id,
        len(BOT_REPLIES)
    )

    await message.reply(
        BOT_REPLIES[index]
    )

async def main():
    await init_db()
    await send_takeoff_notifications()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
