import asyncio
import mimetypes
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

from Reply import (
    COMMAND_AUDIO_START,
    MESSAGES,
)


router = Router(name="audio_router")


def is_supported_media(
    message: Message,
) -> bool:
    if message.video:
        return True

    if message.document:
        mime = (
            message.document.mime_type
            or ""
        ).lower()

        if (
            mime.startswith("video/")
            or mime.startswith("audio/")
        ):
            return True

        filename = (
            message.document.file_name
            or ""
        )

        guessed, _ = mimetypes.guess_type(
            filename
        )

        if guessed and (
            guessed.startswith("video/")
            or guessed.startswith("audio/")
        ):
            return True

    return False


def get_media(
    message: Message,
):
    return message.video or message.document


def get_media_file_id(
    message: Message,
):
    media = get_media(message)

    if not media:
        return None

    return media.file_id


async def download_media(
    message: Message,
    file_id: str,
    output_path: Path,
):
    file_info = await message.bot.get_file(
        file_id
    )

    await message.bot.download_file(
        file_info.file_path,
        destination=output_path,
    )


async def has_audio_stream(
    input_path: Path,
) -> bool:
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(input_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    stdout, _ = await process.communicate()

    return (
        process.returncode == 0
        and bool(stdout.strip())
    )


async def convert_to_voice(
    source: Path,
    target: Path,
) -> bool:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-c:a",
        "libopus",
        "-f",
        "ogg",
        str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    code = await process.wait()

    return (
        code == 0
        and target.exists()
        and target.stat().st_size > 0
    )


async def extract_audio(
    message: Message,
):
    replied = message.reply_to_message

    if not replied:
        return

    if not is_supported_media(replied):
        return

    file_id = get_media_file_id(
        replied
    )

    if not file_id:
        return

    status = None

    try:
        status = await message.reply(
            MESSAGES[
                "audio_extract_started"
            ]
        )

        with tempfile.TemporaryDirectory(
            prefix="audio_"
        ) as temp_dir:
            workdir = Path(temp_dir)

            source = workdir / "source"
            output = workdir / "voice.ogg"

            await download_media(
                message,
                file_id,
                source,
            )

            if not await has_audio_stream(
                source
            ):
                raise RuntimeError(
                    "no audio stream"
                )

            if not await convert_to_voice(
                source,
                output
            ):
                raise RuntimeError(
                    "voice conversion failed"
                )

            await message.reply_voice(
                voice=FSInputFile(
                    output,
                    filename="voice.ogg",
                )
            )

    except Exception:
        await message.reply(
            MESSAGES[
                "audio_extract_failed"
            ]
        )

    finally:
        if status:
            try:
                await status.delete()
            except Exception:
                pass


@router.message(
    F.text.casefold()
    == COMMAND_AUDIO_START.casefold(),
    F.reply_to_message,
)
async def start_audio_extraction(
    message: Message,
):
    await extract_audio(message)