import os
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    FSInputFile,
    InputMediaDocument,
    ReplyParameters
)

from Reply import (
    TAKEOFF_MESSAGE,
    EDIT_TRIGGER,
    EDIT_MESSAGE,
    BOT_REPLIES,
    DOWNLOAD_STARTED,
    DOWNLOAD_ERROR
)

from CAsh import (
    init_db,
    get_mode,
    save_edit_permission,
    get_next_reply,
    get_file_cache,
    create_file_cache,
    save_file_cache_items,
    delete_file_cache,
    add_download,
    get_next_queued_download,
    finish_download,
    fail_download
)

from bUTToN import (
    mode_keyboard,
    register_button_handlers
)

from yTFMe import (
    cleanup_path,
    get_virtual,
    get_voice
)

from ediT import (
    handle_voice_edit_command,
    handle_voice_edit_duration,
    get_thread_id
)


TOKEN = os.getenv("BOT_TOKEN")
boT_TAkeoFF = os.getenv("boT_TAkeoFF")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()

register_button_handlers(
    dp,
    bot
)


def is_private_message(message: Message):
    return message.chat.type == "private"


def get_scope_id(message: Message):
    if not is_private_message(message):
        return None

    thread_id = message.message_thread_id

    if thread_id:
        return (
            f"private:{message.chat.id}"
            f":topic:{thread_id}"
        )

    return f"private:{message.chat.id}"


def get_job_thread_id(job):
    scope_id = job["scope_id"]

    if not scope_id.startswith("private:"):
        return None

    return job["message_thread_id"]


def get_reply_parameters(job):
    return ReplyParameters(
        message_id=job["message_id"]
    )


def is_link(text):
    if not text:
        return False

    lowered = text.lower()

    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("www.")
        or "t.me/" in lowered
    )


def get_actor_id(message: Message):
    if message.from_user:
        return message.from_user.id

    return message.chat.id


async def send_takeoff_notifications():
    if not boT_TAkeoFF:
        return

    chat_ids = [
        cid.strip()
        for cid in boT_TAkeoFF.split("/")
        if cid.strip()
    ]

    for chat_id in chat_ids:
        try:
            await bot.send_message(
                chat_id=int(chat_id),
                text=TAKEOFF_MESSAGE
            )
        except Exception:
            pass


async def send_cached_item(
    message: Message,
    item
):
    if not is_private_message(message):
        return

    reply_parameters = ReplyParameters(
        message_id=message.message_id
    )

    if item["file_type"] == "document":
        return await bot.send_document(
            chat_id=message.chat.id,
            document=item["file_id"],
            message_thread_id=get_thread_id(
                message
            ),
            reply_parameters=reply_parameters
        )

    if item["file_type"] == "voice":
        return await bot.send_voice(
            chat_id=message.chat.id,
            voice=item["file_id"],
            message_thread_id=get_thread_id(
                message
            ),
            reply_parameters=reply_parameters
        )

    return None


async def send_cached_virtual(
    message: Message,
    items
):
    if not is_private_message(message):
        return

    groups = []
    current_group = []
    current_media_group_id = None

    for item in items:
        media_group_id = item["media_group_id"]

        if media_group_id is None:
            if current_group:
                groups.append(current_group)
                current_group = []
                current_media_group_id = None

            groups.append([item])
            continue

        if (
            current_group
            and media_group_id != current_media_group_id
        ):
            groups.append(current_group)
            current_group = []

        current_media_group_id = media_group_id
        current_group.append(item)

    if current_group:
        groups.append(current_group)

    for group in groups:
        if len(group) == 1:
            await send_cached_item(
                message,
                group[0]
            )
            continue

        for index in range(0, len(group), 10):
            batch = group[index:index + 10]

            if len(batch) == 1:
                await send_cached_item(
                    message,
                    batch[0]
                )
                continue

            media = [
                InputMediaDocument(
                    media=item["file_id"]
                )
                for item in batch
            ]

            await bot.send_media_group(
                chat_id=message.chat.id,
                media=media,
                message_thread_id=get_thread_id(
                    message
                ),
                reply_parameters=ReplyParameters(
                    message_id=message.message_id
                )
            )


async def send_cached_voice(
    message: Message,
    items
):
    if not is_private_message(message):
        return

    for item in items:
        await bot.send_voice(
            chat_id=message.chat.id,
            voice=item["file_id"],
            message_thread_id=get_thread_id(
                message
            ),
            reply_parameters=ReplyParameters(
                message_id=message.message_id
            )
        )


async def send_cached_items(
    message: Message,
    mode,
    items
):
    if not is_private_message(message):
        return

    if mode == "virtual":
        await send_cached_virtual(
            message,
            items
        )
        return

    await send_cached_voice(
        message,
        items
    )


async def send_virtual_files(
    message: Message,
    file_paths
):
    if not is_private_message(message):
        return

    for index in range(0, len(file_paths), 10):
        batch = file_paths[index:index + 10]

        if len(batch) == 1:
            await bot.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(batch[0]),
                message_thread_id=get_thread_id(
                    message
                ),
                reply_parameters=ReplyParameters(
                    message_id=message.message_id
                )
            )
            continue

        media = [
            InputMediaDocument(
                media=FSInputFile(file_path)
            )
            for file_path in batch
        ]

        await bot.send_media_group(
            chat_id=message.chat.id,
            media=media,
            message_thread_id=get_thread_id(
                message
            ),
            reply_parameters=ReplyParameters(
                message_id=message.message_id
            )
        )


async def send_voice_files(
    message: Message,
    file_paths
):
    if not is_private_message(message):
        return

    for file_path in file_paths:
        await bot.send_voice(
            chat_id=message.chat.id,
            voice=FSInputFile(file_path),
            message_thread_id=get_thread_id(
                message
            ),
            reply_parameters=ReplyParameters(
                message_id=message.message_id
            )
        )


async def send_download_result(
    message: Message,
    mode,
    file_paths
):
    if not is_private_message(message):
        return

    if mode == "virtual":
        await send_virtual_files(
            message,
            file_paths
        )
        return

    await send_voice_files(
        message,
        file_paths
    )


async def send_job_message(
    job,
    text
):
    if not job["scope_id"].startswith("private:"):
        return

    await bot.send_message(
        chat_id=job["chat_id"],
        text=text,
        message_thread_id=get_job_thread_id(job),
        reply_parameters=get_reply_parameters(job)
    )


async def create_cache_from_result(
    job,
    sent_messages
):
    scope_id = job["scope_id"]

    if not scope_id.startswith("private:"):
        return

    cache_id = await create_file_cache(
        job["source_url"],
        job["mode"],
        asyncio.get_running_loop().time(),
        scope_id
    )

    if cache_id is None:
        return

    items = []

    for index, sent_message in enumerate(sent_messages):
        file_type = None
        file_id = None
        media_group_id = sent_message.media_group_id

        if job["mode"] == "virtual":
            if sent_message.document:
                file_type = "document"
                file_id = sent_message.document.file_id
        else:
            if sent_message.voice:
                file_type = "voice"
                file_id = sent_message.voice.file_id

        if file_type and file_id:
            items.append(
                {
                    "file_type": file_type,
                    "file_id": file_id,
                    "media_group_id": media_group_id,
                    "item_index": index
                }
            )

    await save_file_cache_items(
        cache_id,
        items
    )


async def send_virtual_files_and_cache(
    job,
    file_paths
):
    if not job["scope_id"].startswith("private:"):
        return []

    sent_messages = []
    thread_id = get_job_thread_id(job)

    for index in range(0, len(file_paths), 10):
        batch = file_paths[index:index + 10]
        reply_parameters = get_reply_parameters(job)

        if len(batch) == 1:
            sent_message = await bot.send_document(
                chat_id=job["chat_id"],
                document=FSInputFile(batch[0]),
                message_thread_id=thread_id,
                reply_parameters=reply_parameters
            )

            sent_messages.append(sent_message)
            continue

        media = [
            InputMediaDocument(
                media=FSInputFile(file_path)
            )
            for file_path in batch
        ]

        sent_group = await bot.send_media_group(
            chat_id=job["chat_id"],
            media=media,
            message_thread_id=thread_id,
            reply_parameters=reply_parameters
        )

        sent_messages.extend(sent_group)

    return sent_messages


async def send_voice_files_and_cache(
    job,
    file_paths
):
    if not job["scope_id"].startswith("private:"):
        return []

    sent_messages = []
    thread_id = get_job_thread_id(job)

    for file_path in file_paths:
        sent_message = await bot.send_voice(
            chat_id=job["chat_id"],
            voice=FSInputFile(file_path),
            message_thread_id=thread_id,
            reply_parameters=get_reply_parameters(job)
        )

        sent_messages.append(sent_message)

    return sent_messages


async def process_download(job):
    if not job["scope_id"].startswith("private:"):
        await fail_download(job["id"])
        return

    job_directory = None

    try:
        await send_job_message(
            job,
            DOWNLOAD_STARTED
        )

        if job["mode"] == "voice":
            job_directory, file_paths = await asyncio.to_thread(
                get_voice,
                job["source_url"]
            )
        else:
            job_directory, file_paths = await asyncio.to_thread(
                get_virtual,
                job["source_url"]
            )

        if job["mode"] == "virtual":
            sent_messages = await send_virtual_files_and_cache(
                job,
                file_paths
            )
        else:
            sent_messages = await send_voice_files_and_cache(
                job,
                file_paths
            )

        await create_cache_from_result(
            job,
            sent_messages
        )

        await finish_download(
            job["id"]
        )

    except Exception:
        await fail_download(
            job["id"]
        )

        try:
            await delete_file_cache(
                job["source_url"],
                job["mode"],
                job["scope_id"]
            )
        except Exception:
            pass

        try:
            await send_job_message(
                job,
                DOWNLOAD_ERROR
            )
        except Exception:
            pass

    finally:
        cleanup_path(job_directory)

        await start_next_download(
            job["scope_id"]
        )


async def start_next_download(
    scope_id
):
    if not isinstance(scope_id, str):
        return

    if not scope_id.startswith("private:"):
        return

    while True:
        job = await get_next_queued_download(
            scope_id
        )

        if job is None:
            return

        asyncio.create_task(
            process_download(job)
        )


async def handle_media_request(
    message: Message,
    url,
    mode
):
    if not is_private_message(message):
        return

    scope_id = get_scope_id(message)

    if scope_id is None:
        return

    cache = await get_file_cache(
        url,
        mode,
        scope_id
    )

    if cache is not None:
        try:
            await send_cached_items(
                message,
                mode,
                cache["items"]
            )
            return
        except Exception:
            await delete_file_cache(
                url,
                mode,
                scope_id
            )

    job = await add_download(
        scope_id=scope_id,
        user_id=get_actor_id(message),
        chat_id=message.chat.id,
        message_id=message.message_id,
        message_thread_id=message.message_thread_id,
        source_url=url,
        mode=mode
    )

    if job is None:
        return

    if job["status"] == "active":
        asyncio.create_task(
            process_download(job)
        )


async def handle_text_message(
    message: Message
):
    if not is_private_message(message):
        return

    if not message.text:
        return

    if await handle_voice_edit_command(
        message
    ):
        return

    if await handle_voice_edit_duration(
        message,
        bot
    ):
        return

    if message.text == EDIT_TRIGGER:
        scope_id = get_scope_id(message)

        if scope_id is None:
            return

        current_mode = await get_mode(
            scope_id
        )

        sent_message = await message.reply(
            EDIT_MESSAGE,
            reply_markup=mode_keyboard(
                current_mode
            )
        )

        if message.from_user:
            await save_edit_permission(
                message.chat.id,
                sent_message.message_id,
                message.from_user.id
            )

        return

    if is_link(message.text):
        scope_id = get_scope_id(message)

        if scope_id is None:
            return

        mode = await get_mode(
            scope_id
        )

        await handle_media_request(
            message,
            message.text,
            mode
        )

        return

    if not message.from_user:
        return

    index = await get_next_reply(
        message.from_user.id,
        len(BOT_REPLIES)
    )

    await message.reply(
        BOT_REPLIES[index]
    )


@dp.message(F.text)
async def text_handler(
    message: Message
):
    await handle_text_message(
        message
    )


async def main():
    await init_db()
    await send_takeoff_notifications()

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )