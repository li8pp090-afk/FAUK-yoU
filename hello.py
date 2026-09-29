import asyncio
import os
import random
import re
import sqlite3
from pathlib import Path

from aiogram import Bot
from aiogram import Dispatcher
from aiogram import F
from aiogram.enums import ChatType
from aiogram.types import FSInputFile
from aiogram.types import ReactionTypeEmoji

import Reply
import bToN
import CAsh
import NAMe
import yTFMe


DEVELOPER_IDS_ENV = "boT_TAkeoFF"
BOT_TOKEN_ENV = "BOT_TOKEN"
DATABASE_PATH = "bot.db"
DOWNLOAD_DIRECTORY = "downloads"
DEFAULT_MODE = "normal"
MAX_MEDIA_GROUP_SIZE = 8

URL_PATTERN = re.compile(
    r"https?://\S+",
    re.IGNORECASE,
)


class DeveloperCycle:
    def __init__(self, developer_ids):
        self.developer_ids = developer_ids
        self.id_index = 0
        self.name_index = 0
        self.style_index = 0
        self.lock = asyncio.Lock()

    async def next(self):
        async with self.lock:
            if not self.developer_ids:
                return None

            result = (
                self.developer_ids[self.id_index],
                Reply.DEVELOPER_NAMES[
                    self.name_index
                ],
                bToN.DEVELOPER_STYLES[
                    self.style_index
                ],
            )

            self.id_index = (
                self.id_index + 1
            ) % len(self.developer_ids)

            self.name_index = (
                self.name_index + 1
            ) % len(Reply.DEVELOPER_NAMES)

            self.style_index = (
                self.style_index + 1
            ) % len(bToN.DEVELOPER_STYLES)

            return result


def load_developer_ids():
    return [
        int(item.strip())
        for item in os.getenv(
            DEVELOPER_IDS_ENV,
            "",
        ).split("/")
        if item.strip()
    ]


def get_database():
    return sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False,
    )


def developer_markup(developer):
    if developer is None:
        return None

    return bToN.create_developer_markup(
        *developer
    )


async def react(
    bot,
    message,
    reaction_index,
):
    delay = Reply.REACTION_DELAYS[
        reaction_index
        % len(Reply.REACTION_DELAYS)
    ]

    await asyncio.sleep(delay)

    emoji = Reply.REACTIONS[
        reaction_index
        % len(Reply.REACTIONS)
    ]

    try:
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[
                ReactionTypeEmoji(
                    emoji=emoji
                )
            ],
        )
    except Exception:
        pass


def schedule_reaction(
    bot,
    message,
    reaction_index,
):
    asyncio.create_task(
        react(
            bot,
            message,
            reaction_index,
        )
    )


async def animate(
    message,
    text,
):
    rendered = []

    for line_index, line in enumerate(
        text.split("\n")
    ):
        words = line.split()

        while len(rendered) <= line_index:
            rendered.append("")

        position = 0
        pattern_index = 0

        while position < len(words):
            minimum, maximum = Reply.TYPE_PATTERNS[
                pattern_index
                % len(Reply.TYPE_PATTERNS)
            ]

            amount = random.randint(
                minimum,
                maximum,
            )

            position = min(
                position + amount,
                len(words),
            )

            rendered[line_index] = " ".join(
                words[:position]
            )

            await message.edit_text(
                "\n".join(rendered)
            )

            await asyncio.sleep(
                Reply.TYPE_DELAY
            )

            pattern_index += 1


async def animated_reply(
    message,
    text,
    developers,
    reaction_index,
):
    sent = await message.reply("")

    await animate(
        sent,
        text,
    )

    developer = await developers.next()

    if developer:
        await sent.edit_reply_markup(
            reply_markup=developer_markup(
                developer
            )
        )

    schedule_reaction(
        message.bot,
        sent,
        reaction_index,
    )

    return sent


async def send_reply(
    message,
    text,
    developers,
    reaction_index,
):
    developer = await developers.next()

    sent = await message.reply(
        text,
        reply_markup=developer_markup(
            developer
        ),
    )

    schedule_reaction(
        message.bot,
        sent,
        reaction_index,
    )

    return sent


async def authorized(message):
    if message.chat.type == ChatType.PRIVATE:
        return True

    if message.chat.type not in (
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ):
        return False

    member = await message.bot.get_chat_member(
        message.chat.id,
        message.from_user.id,
    )

    return member.status in {
        "creator",
        "administrator",
    }


def get_mode(database, message):
    return database.get_mode(
        NAMe.get_mode_scope_key(message),
        DEFAULT_MODE,
    )


def set_mode(
    database,
    message,
    mode,
):
    database.set_mode(
        NAMe.get_mode_scope_key(message),
        mode,
    )


async def send_mode(
    message,
    database,
    developers,
    reaction_index,
):
    mode = get_mode(
        database,
        message,
    )

    sent = await message.reply("")

    await animate(
        sent,
        Reply.MODE_TEXT,
    )

    developer = await developers.next()

    if developer:
        await sent.edit_reply_markup(
            reply_markup=bToN.create_mode_markup(
                mode,
                *developer,
            )
        )

    schedule_reaction(
        message.bot,
        sent,
        reaction_index,
    )


def extract_url(message):
    text = message.text or message.caption

    if not text:
        return None

    match = URL_PATTERN.search(text)

    if not match:
        return None

    url = match.group(0).rstrip(
        ".,!?;:)]}"
    )

    if NAMe.is_telegram_link(url):
        return None

    return url


def get_content_key(info):
    extractor = (
        info.get("extractor_key")
        or info.get("extractor")
        or ""
    )

    content_id = info.get("id")

    if extractor and content_id:
        return f"{extractor}:{content_id}"

    return (
        info.get("webpage_url")
        or info.get("original_url")
        or info.get("url")
        or ""
    )


def get_cached_file(
    database,
    info,
    mode,
):
    key = get_content_key(info)

    if mode == "normal":
        return database.get_normal_file(key)

    return database.get_voice_file(key)


def save_cached_file(
    database,
    info,
    mode,
    sent,
    filename,
):
    key = get_content_key(info)

    if mode == "normal":
        if sent.document is None:
            return

        database.save_normal_file(
            key,
            sent.document.file_id,
            sent.document.file_unique_id,
            filename,
        )
        return

    if sent.voice is None:
        return

    database.save_voice_file(
        key,
        sent.voice.file_id,
        sent.voice.file_unique_id,
        filename,
    )


def get_output_template(
    directory,
    info,
):
    filename = NAMe.build_filename(info)

    if not filename:
        filename = str(
            info.get("id") or "file"
        )

    return str(
        Path(directory)
        / f"{filename}.%(ext)s"
    )


async def download_item(
    url,
    directory,
    info,
    mode,
):
    template = get_output_template(
        directory,
        info,
    )

    if mode == "normal":
        result = await yTFMe.run_normal_download(
            url,
            template,
        )

        video = yTFMe.get_video_download(
            result
        )

        audio = yTFMe.get_audio_download(
            result
        )

        if video and audio:
            video_path = yTFMe.get_download_path(
                video
            )

            audio_path = yTFMe.get_download_path(
                audio
            )

            if not video_path or not audio_path:
                raise RuntimeError

            merged_path = (
                video_path.parent
                / f".{video_path.name}.merged"
            )

            await yTFMe.run_merge(
                video_path,
                audio_path,
                merged_path,
                video,
            )

            os.replace(
                merged_path,
                video_path,
            )

            if audio_path.exists():
                audio_path.unlink()

            return video_path

        if video:
            return yTFMe.get_download_path(
                video
            )

        raise RuntimeError

    result = await yTFMe.run_voice_download(
        url,
        template,
    )

    audio = yTFMe.get_audio_download(
        result
    )

    if not audio:
        raise RuntimeError

    audio_path = yTFMe.get_download_path(
        audio
    )

    if not audio_path:
        raise RuntimeError

    output_path = (
        audio_path.parent
        / f".{audio_path.stem}.voice.ogg"
    )

    result_path = (
        await yTFMe.run_voice_conversion(
            audio_path,
            output_path,
        )
    )

    if audio_path.exists():
        audio_path.unlink()

    return result_path


async def send_cached(
    message,
    file_id,
    mode,
):
    if mode == "normal":
        return await message.reply_document(
            file_id
        )

    return await message.reply_voice(
        file_id
    )


async def send_path(
    message,
    info,
    path,
    mode,
    database,
    reaction_index,
):
    if mode == "normal":
        sent = await message.reply_document(
            FSInputFile(path)
        )
    else:
        sent = await message.reply_voice(
            FSInputFile(path)
        )

    save_cached_file(
        database,
        info,
        mode,
        sent,
        path.name,
    )

    schedule_reaction(
        message.bot,
        sent,
        reaction_index,
    )

    return sent


async def process_url(
    message,
    database,
    developers,
    queue,
    reaction_state,
):
    url = extract_url(message)

    if not url:
        return

    scope = NAMe.get_queue_scope_key(
        message
    )

    reservation = await queue.reserve(scope)

    if reservation is None:
        return

    try:
        if reservation == "waiting":
            await queue.acquire_waiting(scope)

        await send_reply(
            message,
            Reply.DOWNLOAD_START_TEXT,
            developers,
            reaction_state[0],
        )

        reaction_state[0] += 1

        mode = get_mode(
            database,
            message,
        )

        directory = NAMe.create_download_directory(
            DOWNLOAD_DIRECTORY,
            message.from_user.id,
        )

        info = await asyncio.to_thread(
            yTFMe.extract_info,
            url,
        )

        entries = [
            entry
            for entry in info.get(
                "entries",
                [],
            )
            if entry
        ]

        if not entries:
            entries = [info]

        for batch_start in range(
            0,
            len(entries),
            MAX_MEDIA_GROUP_SIZE,
        ):
            batch = entries[
                batch_start:
                batch_start + MAX_MEDIA_GROUP_SIZE
            ]

            for entry in batch:
                cached = get_cached_file(
                    database,
                    entry,
                    mode,
                )

                if cached:
                    sent = await send_cached(
                        message,
                        cached[0],
                        mode,
                    )

                    schedule_reaction(
                        message.bot,
                        sent,
                        reaction_state[0],
                    )

                    reaction_state[0] += 1
                    continue

                entry_url = (
                    entry.get("webpage_url")
                    or entry.get("original_url")
                    or url
                )

                path = await download_item(
                    entry_url,
                    directory,
                    entry,
                    mode,
                )

                if path is None:
                    raise RuntimeError

                await send_path(
                    message,
                    entry,
                    path,
                    mode,
                    database,
                    reaction_state[0],
                )

                reaction_state[0] += 1

    except Exception:
        await send_reply(
            message,
            Reply.DOWNLOAD_FAIL_TEXT,
            developers,
            reaction_state[0],
        )

        reaction_state[0] += 1

    finally:
        await queue.release(scope)


async def handle_callback(
    callback,
    database,
    developers,
    reaction_state,
):
    message = callback.message

    if message is None:
        return

    if not await authorized(message):
        await callback.answer(
            Reply.UNAUTHORIZED_TEXT,
            show_alert=True,
        )
        return

    current = get_mode(
        database,
        message,
    )

    requested = callback.data.split(
        ":",
        1,
    )[1]

    if requested == current:
        requested = (
            "voice"
            if current == "normal"
            else "normal"
        )

    set_mode(
        database,
        message,
        requested,
    )

    await callback.answer()

    developer = await developers.next()

    await message.edit_reply_markup(
        reply_markup=bToN.create_mode_markup(
            requested,
            *developer
            if developer
            else (
                None,
                None,
                None,
            ),
        )
    )


async def handle_message(
    message,
    database,
    developers,
    queue,
    reaction_state,
):
    if message.from_user is None:
        return

    if message.text == Reply.MODE_EDIT:
        if await authorized(message):
            await send_mode(
                message,
                database,
                developers,
                reaction_state[0],
            )

            reaction_state[0] += 1

        return

    url = extract_url(message)

    if url:
        await process_url(
            message,
            database,
            developers,
            queue,
            reaction_state,
        )
        return

    if (
        message.chat.type != ChatType.PRIVATE
        and message.text != Reply.BOT_WORD
    ):
        return

    scope = (
        f"user:{message.from_user.id}"
        if message.chat.type == ChatType.PRIVATE
        else f"chat:{message.chat.id}"
    )

    index = database.next_reply_index(
        scope,
        len(Reply.ROTATING_REPLIES),
    )

    await animated_reply(
        message,
        Reply.ROTATING_REPLIES[index],
        developers,
        reaction_state[0],
    )

    reaction_state[0] += 1


async def startup(
    bot,
    developers,
    reaction_state,
):
    for developer_id in load_developer_ids():
        developer = await developers.next()

        sent = await bot.send_message(
            developer_id,
            Reply.STARTUP_TEXT,
            reply_markup=developer_markup(
                developer
            ),
        )

        schedule_reaction(
            bot,
            sent,
            reaction_state[0],
        )

        reaction_state[0] += 1


async def main():
    bot = Bot(
        token=os.getenv(
            BOT_TOKEN_ENV,
            "",
        )
    )

    dispatcher = Dispatcher()

    database = CAsh.Database(
        get_database()
    )

    developers = DeveloperCycle(
        load_developer_ids()
    )

    queue = NAMe.DownloadQueue()

    reaction_state = [0]

    dispatcher.message.register(
        lambda message: handle_message(
            message,
            database,
            developers,
            queue,
            reaction_state,
        )
    )

    dispatcher.callback_query.register(
        lambda callback: handle_callback(
            callback,
            database,
            developers,
            reaction_state,
        ),
        F.data.startswith("mode:"),
    )

    await startup(
        bot,
        developers,
        reaction_state,
    )

    try:
        await dispatcher.start_polling(
            bot
        )
    finally:
        database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())