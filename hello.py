import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import FSInputFile, Message

from AUdio_3 import setup_audio_handlers
from bUTToN_2 import (
    scope_for_message,
    setup_button_handlers,
)
from CAsh_2 import (
    get_file_record,
    get_mode,
    init_cache_db,
    save_file_record,
)
from ediT_2 import router as edit_router
from NoTice_2 import setup_notice_handlers
from Reply_2 import COMMAND_BOT_TRIGGER, MESSAGES
from SeTTiNGs_2 import (
    build_filename,
    is_ignored_url,
    normalize_url,
    sha256_id,
)
from yTFMe_2 import (
    convert_to_ogg_opus,
    download_with_ytdlp,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "bot.sqlite3")
BOT_TAKEOFF = os.getenv("boT_TAkeoFF", "")

ACTIVE_DOWNLOADS = 3
WAITING_DOWNLOADS = 3

reply_state = {}
reply_state_lock = asyncio.Lock()

download_queue = asyncio.Queue(
    maxsize=WAITING_DOWNLOADS
)

router = Router(name="text_router")


async def init_db():
    await init_cache_db(DB_PATH)


async def send_takeoff_message(bot: Bot):
    if not BOT_TAKEOFF:
        return

    chat_ids = [
        x.strip()
        for x in BOT_TAKEOFF.split("/")
        if x.strip()
    ]

    for chat_id in chat_ids:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=MESSAGES["takeoff"],
            )
        except Exception:
            pass


async def send_saved_file(
    message: Message,
    mode: str,
    file_id: str,
):
    if mode == "voice":
        await message.reply_voice(
            voice=file_id
        )
    else:
        await message.reply_document(
            document=file_id
        )


async def process_url(
    message: Message,
    url: str,
    mode: str,
):
    source_type = "url"
    content_id = sha256_id(url)

    existing = await get_file_record(
        DB_PATH,
        mode,
        source_type,
        content_id,
    )

    if existing:
        await send_saved_file(
            message,
            mode,
            existing[0],
        )
        return

    status = None
    workdir = tempfile.mkdtemp(
        prefix="download_"
    )

    try:
        status = await message.reply(
            MESSAGES["start_download"]
        )

        path, info = await asyncio.to_thread(
            download_with_ytdlp,
            url,
            mode,
            workdir,
        )

        if mode == "voice":
            output = Path(workdir) / "voice.ogg"

            await convert_to_ogg_opus(
                path,
                output,
            )

            sent = await message.reply_voice(
                voice=FSInputFile(output),
            )

            await save_file_record(
                DB_PATH,
                mode,
                source_type,
                content_id,
                sent.voice.file_id,
                "voice.ogg",
            )
        else:
            filename = build_filename(
                info,
                path,
            )

            sent = await message.reply_document(
                document=FSInputFile(
                    path,
                    filename=filename,
                ),
            )

            await save_file_record(
                DB_PATH,
                mode,
                source_type,
                content_id,
                sent.document.file_id,
                filename,
            )

    except Exception:
        await message.reply(
            MESSAGES["fail_download"]
        )

    finally:
        if status:
            try:
                await status.delete()
            except Exception:
                pass

        shutil.rmtree(
            workdir,
            ignore_errors=True,
        )


async def submit_job(
    message: Message,
    value: str,
    mode: str,
):
    try:
        download_queue.put_nowait(
            (
                message,
                value,
                mode,
            )
        )
    except asyncio.QueueFull:
        return


async def rotating_reply(message: Message):
    user_id = message.from_user.id if message.from_user else "channel"

    key = (
        f"{message.chat.id}:"
        f"{user_id}"
    )

    async with reply_state_lock:
        index = reply_state.get(key, 0)

        reply_state[key] = (
            index + 1
        ) % len(
            MESSAGES["bot_replies"]
        )

    await message.reply(
        MESSAGES["bot_replies"][index]
    )


async def worker():
    while True:
        message, value, mode = (
            await download_queue.get()
        )

        try:
            await process_url(
                message,
                value,
                mode,
            )
        finally:
            download_queue.task_done()


@router.message(F.text)
async def text_handler(
    message: Message,
):
    text = (
        message.text or ""
    ).strip()

    if not text:
        return

    url = normalize_url(text)

    if url and not is_ignored_url(url):
        mode = await get_mode(
            DB_PATH,
            scope_for_message(message),
        )

        await submit_job(
            message,
            url,
            mode,
        )

        return

    if (
        message.chat.type == "private"
        or text == COMMAND_BOT_TRIGGER
    ):
        await rotating_reply(message)


@router.channel_post(F.text)
async def channel_text_handler(
    message: Message,
):
    text = (
        message.text or ""
    ).strip()

    if not text:
        return

    url = normalize_url(text)

    if url and not is_ignored_url(url):
        mode = await get_mode(
            DB_PATH,
            scope_for_message(message),
        )

        await submit_job(
            message,
            url,
            mode,
        )

        return

    if text == COMMAND_BOT_TRIGGER:
        await rotating_reply(message)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set"
        )

    await init_db()

    bot = Bot(BOT_TOKEN)
    dispatcher = Dispatcher()

    dispatcher.include_router(
        edit_router
    )

    dispatcher.include_router(
        setup_button_handlers(DB_PATH)
    )

    dispatcher.include_router(
        setup_notice_handlers(DB_PATH)
    )

    dispatcher.include_router(
        setup_audio_handlers(DB_PATH)
    )

    dispatcher.include_router(
        router
    )

    workers = [
        asyncio.create_task(worker())
        for _ in range(ACTIVE_DOWNLOADS)
    ]

    await send_takeoff_message(bot)

    try:
        await dispatcher.start_polling(
            bot
        )
    finally:
        for task in workers:
            task.cancel()

        await asyncio.gather(
            *workers,
            return_exceptions=True,
        )

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
