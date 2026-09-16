import mimetypes
import tempfile
from pathlib import Path

from aiogram.types import (
    FSInputFile,
    InputMediaDocument,
    Message,
)

from CAsh import get_file_record, save_file_record
from Reply import MESSAGES
from yTFMe import convert_to_ogg_opus


def is_media_file(message: Message) -> bool:
    if message.video or message.audio or message.voice:
        return True

    if message.document:
        mime = (
            message.document.mime_type or ""
        ).lower()

        if (
            mime.startswith("audio/")
            or mime.startswith("video/")
        ):
            return True

        file_name = (
            message.document.file_name
            or ""
        )

        guessed_type, _ = (
            mimetypes.guess_type(file_name)
        )

        if guessed_type and (
            guessed_type.startswith("audio/")
            or guessed_type.startswith("video/")
        ):
            return True

    return False


def is_audio_media(message: Message) -> bool:
    if message.audio or message.voice:
        return True

    if message.document:
        mime = (
            message.document.mime_type
            or ""
        ).lower()

        if mime.startswith("audio/"):
            return True

        file_name = (
            message.document.file_name
            or ""
        )

        guessed_type, _ = (
            mimetypes.guess_type(file_name)
        )

        return bool(
            guessed_type
            and guessed_type.startswith("audio/")
        )

    return False


def get_media_name(
    message: Message,
    file_path: str,
) -> str:
    media = (
        message.video
        or message.audio
        or message.document
    )

    if media:
        file_name = getattr(
            media,
            "file_name",
            None,
        )

        if file_name:
            return file_name

    return Path(file_path).name


def unique_album_filename(
    filename: str,
    used_names: set[str],
) -> str:
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix

    candidate = filename
    number = 2

    while candidate in used_names:
        candidate = (
            f"{stem} {number}{suffix}"
        )
        number += 1

    used_names.add(candidate)

    return candidate


async def process_telegram_album(
    messages: list[Message],
    db_path: str,
    mode: str,
):
    messages = [
        message
        for message in messages
        if is_media_file(message)
    ]

    if not messages:
        return

    if mode == "voice":
        messages = [
            message
            for message in messages
            if is_audio_media(message)
        ]

        if not messages:
            return

    with tempfile.TemporaryDirectory(
        prefix="album_"
    ) as temp_dir:
        workdir = Path(temp_dir)
        items = []
        used_names = set()

        for index, message in enumerate(
            messages
        ):
            media = (
                message.video
                or message.audio
                or message.voice
                or message.document
            )

            if not media:
                continue

            content_id = media.file_id

            existing = await get_file_record(
                db_path,
                mode,
                "telegram_media",
                content_id,
            )

            source_name = None

            if existing:
                filename = (
                    existing[1]
                    or "file"
                )

                items.append(
                    (
                        message,
                        None,
                        filename,
                        existing[0],
                    )
                )
                continue

            file_info = (
                await message.bot.get_file(
                    media.file_id,
                )
            )

            source_name = get_media_name(
                message,
                file_info.file_path,
            )

            filename = unique_album_filename(
                source_name,
                used_names,
            )

            input_path = (
                workdir
                / f"{index}_{Path(source_name).name}"
            )

            await message.bot.download_file(
                file_info.file_path,
                destination=input_path,
            )

            items.append(
                (
                    message,
                    input_path,
                    filename,
                    None,
                )
            )

        if mode == "voice":
            for (
                message,
                input_path,
                filename,
                cached_file_id,
            ) in items:
                if cached_file_id:
                    await message.reply_voice(
                        voice=cached_file_id,
                    )
                    continue

                if not input_path:
                    continue

                output_voice = (
                    workdir
                    / f"{input_path.stem}.ogg"
                )

                try:
                    await convert_to_ogg_opus(
                        input_path,
                        output_voice,
                    )

                    sent = await message.reply_voice(
                        voice=FSInputFile(
                            output_voice
                        ),
                    )

                    media = (
                        message.audio
                        or message.voice
                        or message.document
                    )

                    if media and sent.voice:
                        await save_file_record(
                            db_path,
                            mode,
                            "telegram_media",
                            media.file_id,
                            sent.voice.file_id,
                            "voice.ogg",
                        )

                except Exception:
                    await message.reply(
                        MESSAGES["fail_download"],
                    )

            return

        for start in range(
            0,
            len(items),
            10,
        ):
            batch = items[
                start:start + 10
            ]

            media_group = []

            for (
                message,
                input_path,
                filename,
                cached_file_id,
            ) in batch:
                if cached_file_id:
                    media_group.append(
                        InputMediaDocument(
                            media=cached_file_id,
                        )
                    )
                elif input_path:
                    media_group.append(
                        InputMediaDocument(
                            media=FSInputFile(
                                input_path,
                                filename=filename,
                            )
                        )
                    )

            if not media_group:
                continue

            sent_messages = (
                await messages[0]
                .reply_media_group(
                    media=media_group,
                )
            )

            sent_index = 0

            for (
                message,
                input_path,
                filename,
                cached_file_id,
            ) in batch:
                if cached_file_id:
                    continue

                if (
                    not input_path
                    or sent_index
                    >= len(sent_messages)
                ):
                    continue

                sent = sent_messages[
                    sent_index
                ]
                sent_index += 1

                media = (
                    message.video
                    or message.audio
                    or message.voice
                    or message.document
                )

                if (
                    media
                    and sent.document
                ):
                    await save_file_record(
                        db_path,
                        mode,
                        "telegram_media",
                        media.file_id,
                        sent.document.file_id,
                        filename,
                    )


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

    with tempfile.TemporaryDirectory(
        prefix="media_"
    ) as temp_dir:
        workdir = Path(temp_dir)

        try:
            file_info = (
                await message.bot.get_file(
                    media.file_id,
                )
            )

            input_path = (
                workdir
                / Path(
                    file_info.file_path
                ).name
            )

            output_voice = (
                workdir / "voice.ogg"
            )

            await message.bot.download_file(
                file_info.file_path,
                destination=input_path,
            )

            await convert_to_ogg_opus(
                input_path,
                output_voice,
            )

            sent = await message.reply_voice(
                voice=FSInputFile(
                    output_voice
                ),
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