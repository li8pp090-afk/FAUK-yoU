import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import FSInputFile, Message

from AUdio import router as audio_router
from bUTToN import (
    scope_for_message,
    setup_button_handlers,
)
from CAsh import (
    get_file_record,
    get_mode,
    init_cache_db,
    save_file_record,
)
from ediT import router as edit_router
from Reply import COMMAND_BOT_TRIGGER, MESSAGES
from SeTTiNGs import (
    build_filename,
    is_ignored_url,
    normalize_url,
    sha256_id,
)
from yTFMe import (
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
    init_cache_db(DB_PATH)


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

    existing = get_file_record(
        DB_PATH,
        mode,
        source_type,
        content_id,
    )

    if existing:
        await send_saved_file(
            message,
            mode,
            existing,
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

            save_file_record(
                DB_PATH,
                mode,
                source_type,
                content_id,
                sent.voice.file_id,
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

            save_file_record(
                DB_PATH,
                mode,
                source_type,
                content_id,
                sent.document.file_id,
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
    user_id = (
        message.from_user.id
        if message.from_user
        else "user"
    )

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
        mode = get_mode(
            DB_PATH,
            scope_for_message(message),
        )

        await submit_job(
            message,
            url,
            mode,
        )

        return

    if message.chat.type == "private":
        if text == COMMAND_BOT_TRIGGER:
            await rotating_reply(message)