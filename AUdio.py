import shutil
import tempfile
from pathlib import Path

from aiogram.types import FSInputFile, Message

from CAsh import get_file_record, save_file_record
from Reply import MESSAGES
from yTFMe import convert_to_ogg_opus


async def process_telegram_media(
    message: Message,
    db_path: str,
):
    media = (
        message.video
        or message.audio
        or message.voice
        or message.document
        or message.animation
    )

    if not media:
        return

    if message.document and not (
        (message.document.mime_type or "").startswith("audio/")
        or (message.document.mime_type or "").startswith("video/")
    ):
        return

    content_id = media.file_id

    existing = await get_file_record(
        db_path,
        "voice",
        "telegram_media",
        content_id,
    )

    if existing:
        await message.reply_voice(
            voice=existing[0],
        )
        return

    status = await message.reply(
        MESSAGES["start_download"],
    )

    workdir = tempfile.mkdtemp(
        prefix="media_",
    )

    try:
        file_info = await message.bot.get_file(
            media.file_id,
        )

        input_path = (
            Path(workdir)
            / Path(file_info.file_path).name
        )

        await message.bot.download_file(
            file_info.file_path,
            destination=input_path,
        )

        output_voice = (
            Path(workdir)
            / "voice.ogg"
        )

        await convert_to_ogg_opus(
            input_path,
            output_voice,
        )

        sent = await message.reply_voice(
            voice=FSInputFile(output_voice),
        )

        await save_file_record(
            db_path,
            "voice",
            "telegram_media",
            content_id,
            sent.voice.file_id,
            "voice.ogg",
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


async def handle_media_message(
    message: Message,
    db_path: str,
):
    await process_telegram_media(
        message,
        db_path,
    )