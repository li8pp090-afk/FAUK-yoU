import asyncio
import os
import re
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InputMediaVideo, Message

import CAsh
import Reply
from NAMe import (
    QUEUE,
    build_filename,
    cleanup_task_directory,
    create_task_directory,
    extract_url,
    is_telegram_url,
    scope_for_message,
)
from bToN import MODE_NORMAL, MODE_VOICE, change_mode, mode_keyboard
from yTFMe import download_normal, download_voice

router = Router()

BOT_TOKEN = os.getenv("BOT_TOKEN")
STARTUP_RECIPIENTS = os.getenv("boT_TAkeoFF", "")


def _startup_ids():
    result = []

    for value in STARTUP_RECIPIENTS.split("/"):
        value = value.strip()

        if value and re.fullmatch(r"-?\d+", value):
            result.append(int(value))

    return result


def _is_group(message):
    return message.chat.type in {"group", "supergroup"}


async def _is_moderator(message):
    if not message.from_user:
        return False

    if message.chat.type == "private":
        return True

    member = await message.bot.get_chat_member(
        message.chat.id,
        message.from_user.id,
    )

    return member.status in {
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    }


def _cache_key(info, mode):
    extractor = info.get("extractor_key") or info.get("extractor") or ""
    content_id = info.get("id") or ""
    webpage_url = info.get("webpage_url") or ""

    return f"{mode}:{extractor}:{content_id}:{webpage_url}"


async def _send_download_start(message):
    await message.reply(Reply.DOWNLOAD_START)


async def _send_download_fail(message):
    await message.reply(Reply.DOWNLOAD_FAIL)


async def _send_video(message, path, filename):
    target = Path(path)
    final_path = target.with_name(filename + target.suffix)

    if target != final_path:
        target.replace(final_path)

    sent = await message.reply_video(
        FSInputFile(final_path)
    )

    return sent.video.file_id


async def _send_voice(message, path):
    sent = await message.reply_voice(
        FSInputFile(path)
    )

    return sent.voice.file_id


async def _process_single(message, url, mode, work_dir):
    if is_telegram_url(url):
        return

    if mode == MODE_VOICE:
        path, info = await asyncio.to_thread(
            download_voice,
            url,
            work_dir,
        )

        cache_key = _cache_key(info, mode)
        cached = CAsh.get_file_id(cache_key)

        if cached:
            try:
                sent = await message.reply_voice(cached[0])
                return sent.voice.file_id
            except TelegramBadRequest:
                pass

        file_id = await _send_voice(message, path)

        CAsh.set_file_id(
            cache_key,
            file_id,
            "voice",
        )

        return file_id

    path, info = await asyncio.to_thread(
        download_normal,
        url,
        work_dir,
    )

    cache_key = _cache_key(info, mode)
    cached = CAsh.get_file_id(cache_key)

    if cached:
        try:
            sent = await message.reply_video(cached[0])
            return sent.video.file_id
        except TelegramBadRequest:
            pass

    filename = build_filename(info)

    file_id = await _send_video(
        message,
        path,
        filename,
    )

    CAsh.set_file_id(
        cache_key,
        file_id,
        "video",
    )

    return file_id


async def _process_playlist(message, url, mode, work_dir):
    import yt_dlp

    def extract():
        options = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "extract_flat": True,
            "skip_download": True,
            "noplaylist": False,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(
                url,
                download=False,
            )

    info = await asyncio.to_thread(extract)

    entries = info.get("entries") or []
    urls = []

    for entry in entries:
        if not entry:
            continue

        item_url = (
            entry.get("webpage_url")
            or entry.get("url")
        )

        if item_url and not is_telegram_url(item_url):
            urls.append(item_url)

    if not urls:
        raise RuntimeError("No playlist entries")

    if mode == MODE_VOICE:
        for index, item_url in enumerate(urls):
            item_dir = work_dir / f"item_{index}"
            item_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            await _process_single(
                message,
                item_url,
                mode,
                item_dir,
            )

        return

    for batch_start in range(0, len(urls), 8):
        batch = urls[
            batch_start:batch_start + 8
        ]

        prepared = []

        for index, item_url in enumerate(batch):
            item_dir = work_dir / f"item_{batch_start + index}"

            item_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            path, item_info = await asyncio.to_thread(
                download_normal,
                item_url,
                item_dir,
            )

            cache_key = _cache_key(
                item_info,
                mode,
            )

            cached = CAsh.get_file_id(cache_key)

            if cached:
                prepared.append(
                    (
                        "cached",
                        cached[0],
                        item_info,
                        None,
                    )
                )
                continue

            filename = build_filename(item_info)

            final_path = Path(path).with_name(
                filename + Path(path).suffix
            )

            Path(path).replace(final_path)

            prepared.append(
                (
                    "file",
                    None,
                    item_info,
                    final_path,
                )
            )

        if not prepared:
            continue

        media = []
        upload_indices = []

        for position, item in enumerate(prepared):
            kind, file_id, item_info, final_path = item

            if kind == "cached":
                media.append(
                    InputMediaVideo(
                        media=file_id
                    )
                )
            else:
                media.append(
                    InputMediaVideo(
                        media=FSInputFile(final_path)
                    )
                )

                upload_indices.append(position)

        sent_messages = await message.reply_media_group(
            media=media
        )

        for position in upload_indices:
            sent = sent_messages[position]
            item_info = prepared[position][2]

            cache_key = _cache_key(
                item_info,
                mode,
            )

            CAsh.set_file_id(
                cache_key,
                sent.video.file_id,
                "video",
            )


async def _process_url(message, url):
    if is_telegram_url(url):
        return

    scope = scope_for_message(message)
    acquired = await QUEUE.acquire(scope)

    if not acquired:
        return

    work_dir = None

    try:
        mode = CAsh.get_mode(scope)

        work_dir = create_task_directory(
            message.from_user.id
        )

        await _send_download_start(message)

        import yt_dlp

        def inspect():
            options = {
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "extract_flat": True,
                "skip_download": True,
                "noplaylist": False,
            }

            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.extract_info(
                    url,
                    download=False,
                )

        info = await asyncio.to_thread(inspect)

        if info.get("_type") == "playlist":
            await _process_playlist(
                message,
                url,
                mode,
                work_dir,
            )
        else:
            await _process_single(
                message,
                url,
                mode,
                work_dir,
            )

    except Exception:
        await _send_download_fail(message)

    finally:
        cleanup_task_directory(work_dir)
        await QUEUE.release(scope)


@router.message(CommandStart())
async def start_handler(message: Message):
    return


@router.message(F.text == Reply.EDIT_WORD)
async def edit_handler(message: Message):
    if not await _is_moderator(message):
        if _is_group(message):
            return

    scope = scope_for_message(message)

    await message.reply(
        Reply.EDIT_TEXT,
        reply_markup=mode_keyboard(scope),
    )


@router.callback_query(F.data.startswith("mode:"))
async def mode_callback(callback: CallbackQuery):
    message = callback.message

    if not message:
        await callback.answer()
        return

    if not await _is_moderator(message):
        await callback.answer(
            Reply.UNAUTHORIZED_EDIT,
            show_alert=True,
        )
        return

    requested = callback.data.split(
        ":",
        1,
    )[1]

    if requested not in {
        MODE_NORMAL,
        MODE_VOICE,
    }:
        await callback.answer()
        return

    scope = scope_for_message(message)

    change_mode(
        scope,
        requested,
    )

    await callback.message.edit_reply_markup(
        reply_markup=mode_keyboard(scope)
    )

    await callback.answer()


@router.message()
async def message_handler(message: Message):
    text = message.text or ""
    url = extract_url(text)

    if url:
        await _process_url(
            message,
            url,
        )
        return

    if _is_group(message):
        if text != Reply.BOT_WORD:
            return
    elif text == Reply.EDIT_WORD:
        return

    reply = CAsh.next_reply(
        message.from_user.id,
        Reply.REPLIES,
    )

    await message.reply(reply)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set"
        )

    CAsh.init_db()

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    for recipient_id in _startup_ids():
        try:
            await bot.send_message(
                recipient_id,
                Reply.STARTUP,
            )
        except (
            TelegramForbiddenError,
            TelegramBadRequest,
        ):
            pass

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())