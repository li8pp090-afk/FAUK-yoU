import asyncio
import mimetypes
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.types import (
    FSInputFile,
    InputMediaDocument,
    Message,
)

from CAsh import get_file_record, get_mode, save_file_record
from Reply import MESSAGES
from yTFMe import convert_to_ogg_opus

router = Router(name="audio_media_router")

album_messages = {}
album_tasks = {}
album_lock = asyncio.Lock()


def scope_for_message(message: Message) -> str:
    if message.chat.type == "private":
        return f"user:{message.chat.id}"

    if message.chat.type == "channel":
        return f"channel:{message.chat.id}"

    thread_id = getattr(message, "message_thread_id", None)
    if thread_id:
        return f"chat:{message.chat.id}:topic:{thread_id}"

    return f"chat:{message.chat.id}"


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
    scope = scope_for_message(message)
    mode = await get_mode(db_path, scope)

    existing = await get_file_record(
        db_path,
        mode,
        "telegram_media",
        content_id,
    )

    if existing:
        if mode == "voice":
            await message.reply_voice(
                voice=existing[0],
            )
        else:
            await message.reply_document(
                document=existing[0],
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

            await message.bot.download_file(
                file_info.file_path,
                destination=input_path,
            )

            if mode == "voice":
                output_voice = (
                    workdir / "voice.ogg"
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
                    mode,
                    "telegram_media",
                    content_id,
                    sent.voice.file_id,
                    "voice.ogg",
                )
            else:
                filename = get_media_name(
                    message,
                    file_info.file_path,
                )

                sent = await message.reply_document(
                    document=FSInputFile(
                        input_path,
                        filename=filename,
                    ),
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


async def finish_album(key, db_path: str):
    try:
        await asyncio.sleep(0.12)

        async with album_lock:
            messages = album_messages.pop(
                key,
                [],
            )

            album_tasks.pop(
                key,
                None,
            )

        if not messages:
            return

        mode = await get_mode(
            db_path,
            scope_for_message(
                messages[0]
            ),
        )

        await process_telegram_album(
            messages,
            db_path,
            mode,
        )

    except asyncio.CancelledError:
        raise


async def collect_album(
    message: Message,
    db_path: str,
):
    album_id = message.media_group_id

    if not album_id:
        return

    key = (
        message.chat.id,
        album_id,
    )

    async with album_lock:
        album_messages.setdefault(
            key,
            [],
        ).append(message)

        task = album_tasks.get(key)

        if task and not task.done():
            task.cancel()

        album_tasks[key] = (
            asyncio.create_task(
                finish_album(key, db_path)
            )
        )


def setup_audio_handlers(db_path: str) -> Router:
    @router.message(
        F.video
        | F.audio
        | F.voice
        | F.document
    )
    async def media_handler(
        message: Message,
    ):
        if message.media_group_id:
            await collect_album(message, db_path)
            return

        await handle_media_message(
            message,
            db_path,
        )

    @router.channel_post(
        F.video
        | F.audio
        | F.voice
        | F.document
    )
    async def channel_media_handler(
        message: Message,
    ):
        if message.media_group_id:
            await collect_album(message, db_path)
            return

        await handle_media_message(
            message,
            db_path,
        )

    return router
