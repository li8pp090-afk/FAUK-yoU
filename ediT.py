from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.types import FSInputFile, Message

from Reply import COMMAND_EDIT_AUDIO, MESSAGES
from yTFMe import cut_audio_segment


router = Router(name="edit_voice_router")

EDIT_SESSIONS: dict[tuple[int, int, int], str] = {}

TIME_PATTERN = re.compile(r"^(?:(\d+)\.)?(\d+):(\d{1,2})$")


def parse_time(value: str) -> int | None:
    value = value.strip().replace(" ", "")
    match = TIME_PATTERN.fullmatch(value)

    if not match:
        return None

    hours, minutes, seconds = match.groups()
    hours = int(hours or 0)
    minutes = int(minutes)
    seconds = int(seconds)

    if minutes >= 60 or seconds >= 60:
        return None

    return hours * 3600 + minutes * 60 + seconds


def parse_range(text: str) -> tuple[int, int] | None:
    parts = re.split(r"\s*/\s*", text.strip())

    if len(parts) != 2:
        return None

    start = parse_time(parts[0])
    end = parse_time(parts[1])

    if start is None or end is None or end <= start:
        return None

    return start, end


def get_audio_file_id(message: Message) -> str | None:
    if message.voice:
        return message.voice.file_id

    if message.audio:
        return message.audio.file_id

    if message.document:
        mime_type = message.document.mime_type or ""
        if mime_type.startswith("audio/"):
            return message.document.file_id

    return None


def get_session_key(message: Message) -> tuple[int, int, int]:
    user_id = message.from_user.id if message.from_user else 0
    thread_id = getattr(message, "message_thread_id", None) or 0
    return message.chat.id, user_id, thread_id


async def download_audio(
    bot: Bot,
    file_id: str,
    path: Path,
):
    file = await bot.get_file(file_id)
    await bot.download_file(
        file.file_path,
        destination=path,
    )


async def create_edited_voice(
    bot: Bot,
    message: Message,
    file_id: str,
    start: int,
    end: int,
):
    with tempfile.TemporaryDirectory(prefix="edit_") as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "source"
        output_path = temp_path / "edited.ogg"

        await download_audio(
            bot,
            file_id,
            source_path,
        )

        duration = end - start
        success = await cut_audio_segment(
            source_path=source_path,
            output_path=output_path,
            start=start,
            duration=duration,
        )

        if not success:
            await message.reply(MESSAGES["edit_duration_invalid"])
            return False

        await message.reply_voice(
            voice=FSInputFile(output_path),
        )

        return True


@router.message(
    F.chat.type.in_({ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL}),
    F.reply_to_message,
    F.text.casefold() == COMMAND_EDIT_AUDIO,
)
@router.channel_post(
    F.reply_to_message,
    F.text.casefold() == COMMAND_EDIT_AUDIO,
)
async def start_edit(message: Message):
    replied_message = message.reply_to_message
    if not replied_message:
        return

    file_id = get_audio_file_id(replied_message)
    if not file_id:
        return

    key = get_session_key(message)
    EDIT_SESSIONS[key] = file_id

    await message.reply(MESSAGES["edit_duration_help"])


@router.message(
    F.chat.type.in_({ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL}),
    F.text,
    lambda msg: get_session_key(msg) in EDIT_SESSIONS,
)
@router.channel_post(
    F.text,
    lambda msg: get_session_key(msg) in EDIT_SESSIONS,
)
async def receive_duration(message: Message, bot: Bot):
    key = get_session_key(message)
    file_id = EDIT_SESSIONS.get(key)

    if not file_id:
        return

    try:
        duration_range = parse_range(message.text or "")

        if not duration_range:
            await message.reply(MESSAGES["edit_duration_invalid"])
            return

        start, end = duration_range

        await create_edited_voice(
            bot=bot,
            message=message,
            file_id=file_id,
            start=start,
            end=end,
        )
    finally:
        EDIT_SESSIONS.pop(key, None)
