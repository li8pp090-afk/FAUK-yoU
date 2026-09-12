import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router

from aiogram.types import FSInputFile, Message

from AUdio import handle_media_message
from bUTToN import (
    get_mode,
    init_settings_db,
    scope_for_message,
    setup_button_handlers,
)
from CAsh import (
    get_file_record,
    init_cache_db,
    save_file_record,
)
from NoTice import setup_notice_handlers
from Reply import MESSAGES
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


BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "",
)

DB_PATH = os.getenv(
    "DB_PATH",
    "bot.sqlite3",
)

BOT_TAKEOFF = os.getenv(
    "boT_TAkeoFF",
    "",
)

ACTIVE_DOWNLOADS = 3
WAITING_DOWNLOADS = 3

reply_state = {}
reply_state_lock = asyncio.Lock()

download_queue = asyncio.Queue(
    maxsize=WAITING_DOWNLOADS,
)

router = Router(
    name="media_router",
)


async def init_db():
    await init_settings_db(
        DB_PATH,
    )

    await init_cache_db(
        DB_PATH,
    )


async def send_takeoff_message(
    bot: Bot,
):
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
            voice=file_id,
        )
    else:
        await message.reply_document(
            document=file_id,
        )


async def process_url(
    message: Message,
    url: str,
    mode: str,
):
    source_type = "url"

    content_id = sha256_id(
        url,
    )

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

    status = await message.reply(
        MESSAGES["start_download"],
    )

    workdir = tempfile.mkdtemp(
        prefix="download_",
    )

    try:
        path, info = await asyncio.to_thread(
            download_with_ytdlp,
            url,
            mode,
            workdir,
        )

        if mode == "voice":
            output = (
                Path(workdir)
                / "voice.ogg"
            )

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
            MESSAGES["fail_download"],
        )

    finally:
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


async def rotating_reply(
    message: Message,
):
    if not message.from_user:
        return

    key = (
        f"{message.chat.id}:"
        f"{message.from_user.id}"
    )

    async with reply_state_lock:
        index = reply_state.get(
            key,
            0,
        )

        reply_state[key] = (
            index + 1
        ) % len(
            MESSAGES["bot_replies"]
        )

    await message.reply(
        MESSAGES["bot_replies"][index],
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


@router.message(
    F.video
    | F.audio
    | F.voice
    | F.document
    | F.animation
)
async def media_handler(
    message: Message,
):
    await handle_media_message(
        message,
        DB_PATH,
    )


@router.message(F.text)
async def text_handler(
    message: Message,
):
    text = (
        message.text or ""
    ).strip()

    if not text:
        return

    url = normalize_url(
        text,
    )

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
        or text == "بوت"
    ):
        await rotating_reply(
            message,
        )


@router.channel_post(
    F.video
    | F.audio
    | F.document
    | F.animation
)
async def channel_media_handler(
    message: Message,
):
    await handle_media_message(
        message,
        DB_PATH,
    )


@router.channel_post(F.text)
async def channel_text_handler(
    message: Message,
):
    text = (
        message.text or ""
    ).strip()

    if not text:
        return

    url = normalize_url(
        text,
    )

    if not url or is_ignored_url(url):
        return

    mode = await get_mode(
        DB_PATH,
        scope_for_message(message),
    )

    await submit_job(
        message,
        url,
        mode,
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set"
        )

    await init_db()

    bot = Bot(
        BOT_TOKEN,
    )

    dispatcher = Dispatcher()

    dispatcher.include_router(
        setup_button_handlers(
            DB_PATH,
        )
    )

    dispatcher.include_router(
        setup_notice_handlers(
            DB_PATH,
        )
    )

    dispatcher.include_router(
        router,
    )

    workers = [
        asyncio.create_task(
            worker()
        )
        for _ in range(
            ACTIVE_DOWNLOADS
        )
    ]

    await send_takeoff_message(
        bot,
    )

    try:
        await dispatcher.start_polling(
            bot,
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