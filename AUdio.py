import mimetypes
import tempfile
from pathlib import Path

from aiogram.types import FSInputFile, Message

from CAsh import get_file_record, save_file_record
from Reply import MESSAGES
from yTFMe import convert_to_ogg_opus


def is_media_file(message: Message) -> bool:
    if message.video or message.audio or message.voice:
        return True

    if message.document:
        mime = (message.document.mime_type or "").lower()

        if mime.startswith("audio/") or mime.startswith("video/"):
            return True

        file_name = message.document.file_name or ""
        guessed_type, _ = mimetypes.guess_type(file_name)

        if guessed_type and (
            guessed_type.startswith("audio/")
            or guessed_type.startswith("video/")
        ):
            return True

    return False


async def process_telegram_media(
    message: Message,
    db_path: str,
):
    if not is_media_file(message):
        return

    media = (
        message.video
        or message.audio
        or message.voice
        or message.document
    )

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

    with tempfile.TemporaryDirectory(prefix="media_") as temp_dir:
        workdir = Path(temp_dir)

        try:
            file_info = await message.bot.get_file(
                media.file_id,
            )

            input_path = workdir / Path(file_info.file_path).name
            output_voice = workdir / "voice.ogg"

            await message.bot.download_file(
                file_info.file_path,
                destination=input_path,
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


async def handle_media_message(
    message: Message,
    db_path: str,
):
    await process_telegram_media(
        message,
        db_path,
    )
