import asyncio
import hashlib
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

from aiogram.types import FSInputFile, InputMediaDocument, ReplyParameters

import CAsh
import Reply
import yTFMe


BLOCKED_HOSTS = {
    "youtube.com",
    "youtu.be",
    "telegram.me",
    "t.me"
}


def is_url(value):
    try:
        parsed = urlparse(
            value.strip()
        )

        return (
            parsed.scheme in (
                "http",
                "https"
            )
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def is_blocked_url(url):
    try:
        host = (
            urlparse(url)
            .netloc
            .lower()
            .split(":")[0]
        )

        return any(
            host == domain
            or host.endswith(
                "." + domain
            )
            for domain in BLOCKED_HOSTS
        )

    except Exception:
        return False


def normalize_english(text):
    text = text.lower()

    for char in "atfgujnml":
        text = text.replace(
            char,
            char.upper()
        )

    return text


def clean_name(text):
    text = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        "",
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


async def get_actual_mime(file_path):
    process = await asyncio.create_subprocess_exec(
        "file",
        "--brief",
        "--mime-type",
        "--",
        str(file_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            stderr.decode(
                errors="replace"
            )
        )

    return stdout.decode().strip().lower()


def get_extension_from_mime(mime_type):
    mime_type = (
        mime_type
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    return (
        mimetypes.guess_extension(
            mime_type
        )
        or ""
    )


async def get_real_extension(file_path):
    mime_type = await get_actual_mime(
        file_path
    )

    extension = get_extension_from_mime(
        mime_type
    )

    if not extension:
        raise ValueError(
            "Unable to determine file extension"
        )

    return extension


async def make_filename(
    publisher,
    title,
    file_path
):
    publisher = normalize_english(
        clean_name(publisher)
    )

    title = normalize_english(
        clean_name(title)
    )

    extension = await get_real_extension(
        file_path
    )

    return (
        f"{publisher} - "
        f"{title}"
        f"{extension}"
    )


def rename_file(
    file_path,
    filename
):
    path = Path(file_path)

    final_path = path.with_name(
        filename
    )

    if path != final_path:
        path.rename(
            final_path
        )

    return final_path


def make_file_key(url):
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


async def send_album(
    bot,
    message,
    items
):
    for start in range(
        0,
        len(items),
        8
    ):
        batch = items[
            start:start + 8
        ]

        media = []

        for item in batch:
            cached = await CAsh.get_file_id(
                item["file_key"]
            )

            if cached:
                media.append(
                    InputMediaDocument(
                        media=cached[0]
                    )
                )
            else:
                media.append(
                    InputMediaDocument(
                        media=FSInputFile(
                            item["path"],
                            filename=item["filename"]
                        )
                    )
                )

        try:
            sent_messages = await bot.send_media_group(
                chat_id=message.chat.id,
                media=media,
                reply_parameters=ReplyParameters(
                    message_id=message.message_id
                )
            )

        except Exception:
            for item in batch:
                if item["cached"]:
                    await CAsh.delete_file_id(
                        item["file_key"]
                    )

            media = [
                InputMediaDocument(
                    media=FSInputFile(
                        item["path"],
                        filename=item["filename"]
                    )
                )
                for item in batch
            ]

            sent_messages = await bot.send_media_group(
                chat_id=message.chat.id,
                media=media,
                reply_parameters=ReplyParameters(
                    message_id=message.message_id
                )
            )

        for item, sent_message in zip(
            batch,
            sent_messages
        ):
            if sent_message.document:
                await CAsh.save_file_id(
                    item["file_key"],
                    sent_message.document.file_id,
                    sent_message.document.file_unique_id,
                    item["filename"]
                )


async def process_job(
    bot,
    message,
    url,
    task_id
):
    directory = None

    try:
        await CAsh.update_task(
            task_id,
            "downloading"
        )

        directory = await yTFMe.create_temp_directory()

        entries = await yTFMe.download(
            url,
            directory
        )

        if not entries:
            await message.reply(
                Reply.DOWNLOAD_FAILED_REPLY
            )
            return

        items = []

        for entry in entries:
            entry_url = yTFMe.get_entry_url(
                entry
            )

            if not entry_url:
                continue

            file_key = make_file_key(
                entry_url
            )

            cached = await CAsh.get_file_id(
                file_key
            )

            if cached:
                items.append({
                    "file_key": file_key,
                    "filename": cached[2] or "file",
                    "path": None,
                    "cached": True
                })
                continue

            path = entry.get(
                "_downloaded_path"
            )

            if not path:
                continue

            filename = await make_filename(
                entry.get("uploader")
                or entry.get("channel")
                or entry.get("creator")
                or "unknown",
                entry.get("title")
                or "file",
                path
            )

            final_path = rename_file(
                path,
                filename
            )

            items.append({
                "file_key": file_key,
                "filename": filename,
                "path": final_path,
                "cached": False
            })

        if not items:
            await message.reply(
                Reply.DOWNLOAD_FAILED_REPLY
            )
            return

        await CAsh.update_task(
            task_id,
            "sending"
        )

        await send_album(
            bot,
            message,
            items
        )

    except Exception:
        try:
            await message.reply(
                Reply.DOWNLOAD_FAILED_REPLY
            )
        except Exception:
            pass

    finally:
        if directory:
            await yTFMe.cleanup(
                directory
            )

        await CAsh.delete_task(
            task_id
        )