import shutil
import tempfile
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, Message

from bUTToN import get_mode, scope_for_message
from CAsh import get_file_record, save_file_record
from Reply import MESSAGES
from SeTTiNGs import build_filename
from yTFMe import convert_to_ogg_opus

async def process_telegram_media(
    bot: Bot,
    message: Message,
    mode: str,
    db_path: str,
):
    media = message.video or message.audio or message.voice or message.document
    if not media:
        return

    if message.document and not (
        (message.document.mime_type or "").startswith("audio/")
        or (message.document.mime_type or "").startswith("video/")
    ):
        return

    content_id = media.file_unique_id

    existing = await get_file_record(db_path, mode, "telegram_media", content_id)
    if existing:
        if mode == "voice":
            await message.reply_voice(voice=existing[0])
        else:
            await message.reply_document(
                document=existing[0],
                caption=MESSAGES["default_completion"],
            )
        return

    status = await message.reply(MESSAGES["start_download"])
    workdir = tempfile.mkdtemp(prefix="media_")

    try:
        file_info = await bot.get_file(media.file_id)
        input_path = Path(workdir) / Path(file_info.file_path).name
        await bot.download_file(file_info.file_path, destination=input_path)

        if mode == "voice":
            output_voice = Path(workdir) / "voice.ogg"
            await convert_to_ogg_opus(input_path, output_voice)

            sent = await message.reply_voice(
                voice=FSInputFile(output_voice),
            )

            await save_file_record(
                db_path,
                mode,
                "telegram_media",
                content_id,
                sent.voice.file_id,
                "voice.ogg",
            )
        else:
            filename = getattr(media, "file_name", None) or build_filename({}, input_path)
            sent = await message.reply_document(
                document=FSInputFile(input_path, filename=filename),
                caption=MESSAGES["default_completion"],
            )

            await save_file_record(
                db_path,
                mode,
                "telegram_media",
                content_id,
                sent.document.file_id,
                filename,
            )

    except Exception:
        await message.reply(MESSAGES["fail_download"])

    finally:
        try:
            await status.delete()
        except Exception:
            pass
        shutil.rmtree(workdir, ignore_errors=True)

async def handle_media_message(message: Message, db_path: str):
    mode = await get_mode(db_path, scope_for_message(message))
    await process_telegram_media(message.bot, message, mode, db_path)
