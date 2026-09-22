import re
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

from Reply import (
    COMMAND_EDIT_AUDIO,
    MESSAGES,
)
from yTFMe import cut_audio_segment


router = Router(name="edit_router")

EDIT_SESSIONS = {}


def parse_time(value: str):
    value = value.strip()

    if not value:
        return None

    if ":" in value:
        first, seconds_part = value.split(
            ":",
            1,
        )

        if not first or not seconds_part:
            return None

        if "." in first:
            hour_text, minute_text = first.split(
                ".",
                1,
            )

            if not (
                hour_text.isdigit()
                and minute_text.isdigit()
            ):
                return None

            hours = int(hour_text)
            minutes = int(minute_text)

            if minutes > 59:
                return None
        else:
            if not first.isdigit():
                return None

            hours = 0
            minutes = int(first)

            if minutes > 59:
                return None

        fraction = 0.0

        if "." in seconds_part:
            seconds_text, fraction_text = seconds_part.split(
                ".",
                1,
            )

            if not (
                seconds_text.isdigit()
                and fraction_text.isdigit()
            ):
                return None

            seconds = int(seconds_text)

            if seconds > 59:
                return None

            fraction = int(
                fraction_text
            ) / 60

        else:
            if not seconds_part.isdigit():
                return None

            seconds = int(seconds_part)

            if seconds > 59:
                return None

        return (
            hours * 3600
            + minutes * 60
            + seconds
            + fraction
        )

    if value.isdigit():
        return float(
            int(value)
        )

    return None


def parse_range(text: str):
    text = text.strip()

    if not text:
        return None

    if (
        not re.search(r"\s+/\s+", text)
        and not re.search(r"\s+-\s+", text)
        and not re.search(r"\s+", text)
    ):
        end = parse_time(text)

        if end is None or end <= 0:
            return None

        return 0, end

    if re.search(r"\s+/\s+", text):
        parts = re.split(
            r"\s+/\s+",
            text,
            maxsplit=1,
        )
    elif re.search(r"\s+-\s+", text):
        parts = re.split(
            r"\s+-\s+",
            text,
            maxsplit=1,
        )
    else:
        parts = re.split(
            r"\s+",
            text,
            maxsplit=1,
        )

    if len(parts) != 2:
        return None

    start_text = parts[0].strip()
    end_text = parts[1].strip()

    if not start_text or not end_text:
        return None

    start = parse_time(start_text)
    end = parse_time(end_text)

    if start is None or end is None:
        return None

    if end <= start:
        return None

    return start, end


def get_audio_media(message: Message):
    if message.voice:
        return message.voice

    if message.audio:
        return message.audio

    if message.document:
        return message.document

    return None


async def download_media(
    message: Message,
    media,
    output_path: Path,
):
    file_info = await message.bot.get_file(
        media.file_id
    )

    await message.bot.download_file(
        file_info.file_path,
        destination=output_path,
    )


async def edit_audio(
    message: Message,
    replied: Message,
    start: float,
    end: float,
):
    media = get_audio_media(replied)

    if not media:
        return

    duration = end - start

    with tempfile.TemporaryDirectory(
        prefix="edit_"
    ) as temp_dir:

        workdir = Path(temp_dir)

        source = workdir / "source"
        output = workdir / "edited.ogg"

        try:
            await download_media(
                message,
                media,
                source,
            )

            success = await cut_audio_segment(
                source,
                output,
                start,
                duration,
            )

            if not success:
                return

            await message.reply_voice(
                voice=FSInputFile(
                    output,
                    filename="edited.ogg",
                )
            )

        except Exception:
            return


@router.message(
    F.text.casefold() == COMMAND_EDIT_AUDIO.casefold(),
    F.reply_to_message,
)
async def edit_command(
    message: Message,
):
    EDIT_SESSIONS[
        message.from_user.id
    ] = message.reply_to_message

    await message.answer(
        MESSAGES["edit_duration_help"]
    )


@router.message(F.text)
async def edit_duration(
    message: Message,
):
    user_id = message.from_user.id

    replied = EDIT_SESSIONS.get(
        user_id
    )

    if not replied:
        return

    value = parse_range(
        message.text
    )

    if value is None:
        await message.answer(
            MESSAGES["edit_duration_invalid"]
        )
        return

    start, end = value

    EDIT_SESSIONS.pop(
        user_id,
        None,
    )

    await edit_audio(
        message,
        replied,
        start,
        end,
    )