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
        parts = value.split(":")

        if len(parts) == 2:
            minutes_part, seconds_part = parts[0], parts[1]

            if "." in minutes_part:
                h_m = minutes_part.split(".", 1)
                if not (h_m[0].isdigit() and h_m[1].isdigit()):
                    return None
                hours, minutes = int(h_m[0]), int(h_m[1])
            else:
                if not minutes_part.isdigit():
                    return None
                hours, minutes = 0, int(minutes_part)

            if "." in seconds_part:
                s_f = seconds_part.split(".", 1)
                if not (s_f[0].isdigit() and s_f[1].isdigit()):
                    return None
                seconds = int(s_f[0])
                fraction = float(f"0.{s_f[1]}")
            else:
                if not seconds_part.isdigit():
                    return None
                seconds = int(seconds_part)
                fraction = 0.0

            if minutes > 59 or seconds > 59:
                return None

            return hours * 3600 + minutes * 60 + seconds + fraction

        elif len(parts) == 3:
            hours_part, minutes_part, seconds_part = parts[0], parts[1], parts[2]
            if not (
                hours_part.isdigit()
                and minutes_part.isdigit()
                and seconds_part.isdigit()
            ):
                return None

            hours, minutes, seconds = (
                int(hours_part),
                int(minutes_part),
                int(seconds_part),
            )
            if minutes > 59 or seconds > 59:
                return None

            return hours * 3600 + minutes * 60 + seconds

        return None

    if "." in value:
        parts = value.split(".", 1)
        if parts[0].isdigit() and parts[1].isdigit():
            hours = int(parts[0])
            minutes = int(parts[1])
            if minutes > 59:
                return None
            return hours * 3600 + minutes * 60

    if value.isdigit():
        return float(int(value))

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
        await message.reply(MESSAGES["audio_extract_failed"])
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
                await message.reply(MESSAGES["audio_extract_failed"])
                return

            await message.reply_voice(
                voice=FSInputFile(
                    output,
                    filename="edited.ogg",
                )
            )

        except Exception:
            await message.reply(MESSAGES["audio_extract_failed"])


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

    if user_id not in EDIT_SESSIONS:
        return

    replied = EDIT_SESSIONS.get(user_id)

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
