import os
import re
from typing import Optional, Tuple

from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters
)

from Reply import (
    VOICE_EDIT_TRIGGER,
    AUDIO_EXTRACT_TRIGGER,
    VOICE_EDIT_INFO_BUTTON,
    VOICE_EDIT_START,
    VOICE_EDIT_INVALID,
    VOICE_EDIT_TOO_LONG,
    NO_AUDIO_TRACK_ERROR
)

from yTFMe import (
    cleanup_path,
    edit_voice,
    get_voice_duration
)


TEMP_DIR = "downloads"

os.makedirs(
    TEMP_DIR,
    exist_ok=True
)


def is_private_message(message: Message) -> bool:
    return message.chat.type == "private"


def get_thread_id(message: Message) -> Optional[int]:
    if not is_private_message(message):
        return None

    return message.message_thread_id


def parse_time_part(
    part: str
) -> Optional[float]:
    part = part.strip()

    if ":" in part:
        sub_parts = part.split(":")

        if len(sub_parts) == 2:
            try:
                minutes = float(sub_parts[0])
                seconds = float(sub_parts[1])

                return (
                    minutes * 60
                    + seconds
                )
            except ValueError:
                return None

        if len(sub_parts) == 3:
            try:
                hours = float(sub_parts[0])
                minutes = float(sub_parts[1])
                seconds = float(sub_parts[2])

                return (
                    hours * 3600
                    + minutes * 60
                    + seconds
                )
            except ValueError:
                return None

        return None

    if "." in part and ":" not in part:
        sub_parts = part.split(".")

        if len(sub_parts) == 2:
            try:
                hours = float(sub_parts[0])
                minutes = float(sub_parts[1])

                return (
                    hours * 3600
                    + minutes * 60
                )
            except ValueError:
                pass

    try:
        return float(part)
    except ValueError:
        return None


def parse_duration_string(
    text: str
) -> Optional[Tuple[float, float]]:
    parts = [
        part
        for part in re.split(
            r"[\s/\-]+",
            text.strip()
        )
        if part
    ]

    if len(parts) == 1:
        end_time = parse_time_part(parts[0])

        if (
            end_time is not None
            and 1 <= end_time <= 60
        ):
            return 0.0, end_time

        return None

    if len(parts) == 2:
        start_time = parse_time_part(parts[0])
        end_time = parse_time_part(parts[1])

        if (
            start_time is not None
            and end_time is not None
            and end_time > start_time
        ):
            return start_time, end_time

    return None


async def handle_voice_edit_command(
    message: Message
) -> bool:
    if not is_private_message(message):
        return False

    if not message.text:
        return False

    if message.text.strip() != VOICE_EDIT_TRIGGER:
        return False

    if not message.reply_to_message:
        return False

    reply = message.reply_to_message

    if not reply.voice:
        return False

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=VOICE_EDIT_INFO_BUTTON,
                    callback_data="voice_edit_info"
                )
            ]
        ]
    )

    await message.reply(
        VOICE_EDIT_START,
        reply_markup=keyboard
    )

    return True


async def handle_audio_extract_command(
    message: Message,
    bot
) -> bool:
    if not is_private_message(message):
        return False

    if not message.text:
        return False

    clean_text = (
        message.text
        .strip()
        .replace("ـ", "")
    )

    if clean_text != AUDIO_EXTRACT_TRIGGER:
        return False

    if not message.reply_to_message:
        return False

    reply = message.reply_to_message

    target_file_id = None

    if reply.video:
        target_file_id = reply.video.file_id
    elif reply.audio:
        target_file_id = reply.audio.file_id
    elif reply.document:
        mime = reply.document.mime_type or ""

        if (
            mime.startswith("video/")
            or mime.startswith("audio/")
        ):
            target_file_id = reply.document.file_id

    if not target_file_id:
        return False

    file_info = await bot.get_file(
        target_file_id
    )

    file_path = file_info.file_path

    downloaded_file = await bot.download_file(
        file_path
    )

    temp_input = os.path.join(
        TEMP_DIR,
        f"extract_in_{message.message_id}"
    )

    temp_output = os.path.join(
        TEMP_DIR,
        f"extract_out_{message.message_id}.ogg"
    )

    with open(
        temp_input,
        "wb"
    ) as file:
        file.write(
            downloaded_file.read()
        )

    try:
        total_duration = await _get_duration(
            temp_input
        )

        if (
            total_duration is None
            or total_duration <= 0
        ):
            await message.reply(
                NO_AUDIO_TRACK_ERROR
            )
            return True

        await _edit_voice(
            temp_input,
            0.0,
            total_duration,
            temp_output
        )

        await bot.send_voice(
            chat_id=message.chat.id,
            voice=FSInputFile(temp_output),
            message_thread_id=get_thread_id(message),
            reply_parameters=ReplyParameters(
                message_id=message.message_id
            )
        )

        return True

    except Exception:
        await message.reply(
            VOICE_EDIT_INVALID
        )
        return True

    finally:
        cleanup_path(temp_input)
        cleanup_path(temp_output)


async def handle_voice_edit_duration(
    message: Message,
    bot
) -> bool:
    if not is_private_message(message):
        return False

    if not message.text:
        return False

    if await handle_audio_extract_command(
        message,
        bot
    ):
        return True

    if not message.reply_to_message:
        return False

    reply = message.reply_to_message

    if not reply.voice:
        return False

    parsed_time = parse_duration_string(
        message.text
    )

    if parsed_time is None:
        return False

    start_sec, end_sec = parsed_time

    file_id = reply.voice.file_id

    file_info = await bot.get_file(
        file_id
    )

    file_path = file_info.file_path

    downloaded_file = await bot.download_file(
        file_path
    )

    temp_input = os.path.join(
        TEMP_DIR,
        f"temp_{message.message_id}.ogg"
    )

    temp_output = os.path.join(
        TEMP_DIR,
        f"cut_{message.message_id}.ogg"
    )

    with open(
        temp_input,
        "wb"
    ) as file:
        file.write(
            downloaded_file.read()
        )

    try:
        total_duration = await _get_duration(
            temp_input
        )

        if (
            total_duration is None
            or end_sec > total_duration
        ):
            await message.reply(
                VOICE_EDIT_TOO_LONG
            )
            return True

        await _edit_voice(
            temp_input,
            start_sec,
            end_sec,
            temp_output
        )

        await bot.send_voice(
            chat_id=message.chat.id,
            voice=FSInputFile(temp_output),
            message_thread_id=get_thread_id(message),
            reply_parameters=ReplyParameters(
                message_id=message.message_id
            )
        )

        return True

    except Exception:
        await message.reply(
            VOICE_EDIT_INVALID
        )
        return True

    finally:
        cleanup_path(temp_input)
        cleanup_path(temp_output)


async def _get_duration(
    file_path: str
) -> Optional[float]:
    try:
        return await _run_blocking(
            get_voice_duration,
            file_path
        )
    except Exception:
        return None


async def _edit_voice(
    source_file: str,
    start: float,
    end: float,
    output_file: str
):
    await _run_blocking(
        edit_voice,
        source_file,
        start,
        end,
        output_file
    )


async def _run_blocking(
    function,
    *args
):
    import asyncio

    return await asyncio.to_thread(
        function,
        *args
    )