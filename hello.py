import os
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    FSInputFile,
    InputMediaDocument,
    ReplyParameters,
    ChatMemberUpdated
)

from Reply import (
    TAKEOFF_MESSAGE,
    EDIT_TRIGGER,
    BOT_TRIGGER,
    ENABLE_TRIGGER,
    DISABLE_TRIGGER,
    ENABLE_REPLY,
    DISABLE_REPLY,
    EDIT_MESSAGE,
    BOT_REPLIES,
    DOWNLOAD_STARTED,
    DOWNLOAD_ERROR,
    AUTO_ENABLED_MESSAGE
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
    fail_download,
    get_auto_enable,
    get_chat_enabled,
    set_chat_enabled
)

from bUTToN import (
    mode_keyboard,
    register_button_handlers
)

from yTFMe import (
    get_virtual,
    get_voice
)

from FFMpeG import (
    cleanup_path
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


def get_scope_id(message: Message):
    if message.chat.type == "private":
        thread_id = message.message_thread_id

        if thread_id:
            return (
                f"private:{message.chat.id}"
                f":topic:{thread_id}"
            )

        return (
            f"private:{message.chat.id}"
        )

    if message.chat.type in {
        "group",
        "supergroup"
    }:
        thread_id = message.message_thread_id

        if thread_id:
            return (
                f"chat:{message.chat.id}"
                f":topic:{thread_id}"
            )

        return (
            f"chat:{message.chat.id}"
        )

    if message.chat.type == "channel":
        return (
            f"channel:{message.chat.id}"
        )

    return (
        f"chat:{message.chat.id}"
    )


def get_scope_id_from_chat(
    chat,
    message_thread_id=None
):
    if chat.type in {
        "group",
        "supergroup"
    }:
        if message_thread_id:
            return (
                f"chat:{chat.id}"
                f":topic:{message_thread_id}"
            )

        return (
            f"chat:{chat.id}"
        )

    if chat.type == "channel":
        return (
            f"channel:{chat.id}"
        )

    return (
        f"chat:{chat.id}"
    )


def get_actor_id(message: Message):
    if message.from_user:
        return message.from_user.id

    if message.sender_chat:
        return message.sender_chat.id

    return message.chat.id


def get_job_thread_id(job):
    scope_id = job["scope_id"]

    if (
        scope_id.startswith("chat:")
        or scope_id.startswith("private:")
    ):
        return job["message_thread_id"]

    return None


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


async def is_authorized(message: Message):
    if message.chat.type == "private":
        return True

    if message.chat.type == "channel":
        return True

    if not message.from_user:
        return False

    member = await bot.get_chat_member(
        message.chat.id,
        message.from_user.id
    )

    return member.status in {
        "creator",
        "administrator"
    }


async def send_cached_item(
    message: Message,
    item
):
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
    groups = []
    current_group = []
    current_media_group_id = None

    for item in items:
        media_group_id = item[
            "media_group_id"
        ]

        if media_group_id is None:
            if current_group:
                groups.append(
                    current_group
                )
                current_group = []
                current_media_group_id = None

            groups.append(
                [item]
            )
            continue

        if (
            current_group
            and media_group_id
            != current_media_group_id
        ):
            groups.append(
                current_group
            )
            current_group = []

        current_media_group_id = (
            media_group_id
        )

        current_group.append(
            item
        )

    if current_group:
        groups.append(
            current_group
        )

    for group in groups:
        if len(group) == 1:
            await send_cached_item(
                message,
                group[0]
            )
            continue

        for index in range(
            0,
            len(group),
            10
        ):
            batch = group[
                index:index + 10
            ]

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
    for index in range(
        0,
        len(file_paths),
        10
    ):
        batch = file_paths[
            index:index + 10
        ]

        if len(batch) == 1:
            await bot.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(
                    batch[0]
                ),
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
                media=FSInputFile(
                    file_path
                )
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
    for file_path in file_paths:
        await bot.send_voice(
            chat_id=message.chat.id,
            voice=FSInputFile(
                file_path
            ),
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
    thread_id = get_job_thread_id(
        job
    )

    await bot.send_message(
        chat_id=job["chat_id"],
        text=text,
        message_thread_id=thread_id,
        reply_parameters=get_reply_parameters(
            job
        )
    )


async def create_cache_from_result(
    job,
    sent_messages
):
    cache_id = await create_file_cache(
        job["source_url"],
        job["mode"],
        asyncio.get_running_loop().time()
    )

    if cache_id is None:
        return

    items = []

    for index, sent_message in enumerate(
        sent_messages
    ):
        file_type = None
        file_id = None
        media_group_id = (
            sent_message.media_group_id
        )

        if job["mode"] == "virtual":
            if sent_message.document:
                file_type = "document"
                file_id = (
                    sent_message.document.file_id
                )
        else:
            if sent_message.voice:
                file_type = "voice"
                file_id = (
                    sent_message.voice.file_id
                )

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
    sent_messages = []

    thread_id = get_job_thread_id(
        job
    )

    for index in range(
        0,
        len(file_paths),
        10
    ):
        batch = file_paths[
            index:index + 10
        ]

        reply_parameters = (
            get_reply_parameters(job)
        )

        if len(batch) == 1:
            sent_message = (
                await bot.send_document(
                    chat_id=job["chat_id"],
                    document=FSInputFile(
                        batch[0]
                    ),
                    message_thread_id=thread_id,
                    reply_parameters=reply_parameters
                )
            )

            sent_messages.append(
                sent_message
            )
            continue

        media = [
            InputMediaDocument(
                media=FSInputFile(
                    file_path
                )
            )
            for file_path in batch
        ]

        sent_group = (
            await bot.send_media_group(
                chat_id=job["chat_id"],
                media=media,
                message_thread_id=thread_id,
                reply_parameters=reply_parameters
            )
        )

        sent_messages.extend(
            sent_group
        )

    return sent_messages


async def send_voice_files_and_cache(
    job,
    file_paths
):
    sent_messages = []

    thread_id = get_job_thread_id(
        job
    )

    for file_path in file_paths:
        sent_message = (
            await bot.send_voice(
                chat_id=job["chat_id"],
                voice=FSInputFile(
                    file_path
                ),
                message_thread_id=thread_id,
                reply_parameters=get_reply_parameters(
                    job
                )
            )
        )

        sent_messages.append(
            sent_message
        )

    return sent_messages


async def process_download(job):
    job_directory = None

    try:
        await send_job_message(
            job,
            DOWNLOAD_STARTED
        )

        if job["mode"] == "voice":
            job_directory, file_paths = (
                await asyncio.to_thread(
                    get_voice,
                    job["source_url"]
                )
            )
        else:
            job_directory, file_paths = (
                await asyncio.to_thread(
                    get_virtual,
                    job["source_url"]
                )
            )

        if job["mode"] == "virtual":
            sent_messages = (
                await send_virtual_files_and_cache(
                    job,
                    file_paths
                )
            )
        else:
            sent_messages = (
                await send_voice_files_and_cache(
                    job,
                    file_paths
                )
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
                job["mode"]
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
        cleanup_path(
            job_directory
        )

        await start_next_download(
            job["scope_id"]
        )


async def start_next_download(
    scope_id
):
    while True:
        job = await get_next_queued_download(
            scope_id
        )

        if job is None:
            return

        asyncio.create_task(
            process_download(
                job
            )
        )


async def handle_media_request(
    message: Message,
    url,
    mode
):
    cache = await get_file_cache(
        url,
        mode
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
                mode
            )

    scope_id = get_scope_id(
        message
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
            process_download(
                job
            )
        )


def get_enabled_scope_id(
    message: Message
):
    return get_scope_id(
        message
    )


async def handle_enable_disable(
    message: Message
):
    if message.chat.type == "private":
        return False

    if message.text not in {
        ENABLE_TRIGGER,
        DISABLE_TRIGGER
    }:
        return False

    if not await is_authorized(
        message
    ):
        return True

    enabled = (
        message.text == ENABLE_TRIGGER
    )

    scope_id = get_enabled_scope_id(
        message
    )

    await set_chat_enabled(
        scope_id,
        enabled
    )

    reply_text = (
        ENABLE_REPLY
        if enabled
        else DISABLE_REPLY
    )

    await message.reply(
        reply_text
    )

    return True


@dp.my_chat_member()
async def my_chat_member_handler(
    event: ChatMemberUpdated
):
    if event.chat.type == "private":
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    active_statuses = {
        "member",
        "administrator",
        "creator"
    }

    if old_status in active_statuses:
        return

    if new_status not in active_statuses:
        return

    user_id = event.from_user.id

    auto_enabled = await get_auto_enable(
        user_id
    )

    scope_id = get_scope_id_from_chat(
        event.chat
    )

    await set_chat_enabled(
        scope_id,
        auto_enabled
    )

    if not auto_enabled:
        return

    try:
        await bot.send_message(
            chat_id=event.chat.id,
            text=AUTO_ENABLED_MESSAGE
        )
    except Exception:
        pass


async def handle_text_message(
    message: Message
):
    if not message.text:
        return

    if await handle_enable_disable(
        message
    ):
        return

    if message.chat.type != "private":
        scope_id = get_scope_id(
            message
        )

        if not await get_chat_enabled(
            scope_id
        ):
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
        if not await is_authorized(
            message
        ):
            return

        scope_id = get_scope_id(
            message
        )

        current_mode = await get_mode(
            scope_id
        )

        auto_enabled = True

        if message.from_user:
            auto_enabled = await get_auto_enable(
                message.from_user.id
            )

        sent_message = await message.reply(
            EDIT_MESSAGE,
            reply_markup=mode_keyboard(
                current_mode,
                auto_enabled
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
        scope_id = get_scope_id(
            message
        )

        mode = await get_mode(
            scope_id
        )

        await handle_media_request(
            message,
            message.text,
            mode
        )

        return

    if message.chat.type == "private":
        if not message.from_user:
            return

        index = await get_next_reply(
            message.from_user.id,
            len(BOT_REPLIES)
        )

        await message.reply(
            BOT_REPLIES[index]
        )

        return

    if message.chat.type == "channel":
        return

    if message.text != BOT_TRIGGER:
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


@dp.channel_post(F.text)
async def channel_post_handler(
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
