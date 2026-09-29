import asyncio
import re
from pathlib import Path

from aiogram.enums import ChatType


TELEGRAM_LINK_PATTERN = re.compile(
    r"^(?:https?://)?"
    r"(?:www\.)?"
    r"(?:t\.me|telegram\.me|telegram\.dog)"
    r"(?:/|$)",
    re.IGNORECASE,
)


class DownloadQueue:
    def __init__(
        self,
        max_active=3,
        max_waiting=3,
    ):
        self.max_active = max_active
        self.max_waiting = max_waiting
        self.states = {}
        self.condition = asyncio.Condition()

    def _get_state(self, scope_key):
        return self.states.setdefault(
            scope_key,
            {
                "active": 0,
                "waiting": 0,
            },
        )

    async def reserve(self, scope_key):
        async with self.condition:
            state = self._get_state(scope_key)

            if state["active"] < self.max_active:
                state["active"] += 1
                return "active"

            if state["waiting"] < self.max_waiting:
                state["waiting"] += 1
                return "waiting"

            return None

    async def acquire_waiting(self, scope_key):
        async with self.condition:
            state = self._get_state(scope_key)

            while state["active"] >= self.max_active:
                await self.condition.wait()

            state["waiting"] -= 1
            state["active"] += 1

    async def release(self, scope_key):
        async with self.condition:
            state = self._get_state(scope_key)

            if state["active"] > 0:
                state["active"] -= 1

            if (
                state["active"] == 0
                and state["waiting"] == 0
            ):
                self.states.pop(
                    scope_key,
                    None,
                )

            self.condition.notify_all()


def get_mode_scope_key(message):
    if message.chat.type == ChatType.PRIVATE:
        return f"private:{message.from_user.id}"

    if (
        message.chat.type == ChatType.SUPERGROUP
        and message.message_thread_id
    ):
        return (
            f"chat:{message.chat.id}:"
            f"topic:{message.message_thread_id}"
        )

    return f"chat:{message.chat.id}"


def get_queue_scope_key(message):
    if message.chat.type == ChatType.PRIVATE:
        return f"user:{message.from_user.id}"

    return f"chat:{message.chat.id}"


def is_telegram_link(url):
    if url.lower().startswith("tg://"):
        return True

    return bool(
        TELEGRAM_LINK_PATTERN.match(url)
    )


def _clean_filename_part(value):
    if not value:
        return ""

    value = str(value).lower()

    result = []

    for character in value:
        if character.isascii():
            if character.isalpha():
                if character.upper() in "ATFGUJNML":
                    result.append(character.upper())
                else:
                    result.append(character)
            elif character.isdigit():
                result.append(character)
            elif character in "_&- ":
                result.append(character)

    return "".join(result).strip()


def _get_video_date(info):
    timestamp = info.get("timestamp")

    if timestamp:
        import datetime

        date = datetime.datetime.fromtimestamp(
            timestamp,
            datetime.timezone.utc,
        )
        return (
            f"{date.year}-"
            f"{date.month}-"
            f"{date.day}"
        )

    upload_date = info.get("upload_date")

    if upload_date and len(upload_date) == 8:
        return (
            f"{upload_date[:4]}-"
            f"{int(upload_date[4:6])}-"
            f"{int(upload_date[6:8])}"
        )

    return ""


def build_filename(info):
    publisher = (
        info.get("publisher")
        or info.get("channel")
        or info.get("uploader")
        or ""
    )

    title = info.get("title") or ""

    publisher = _clean_filename_part(
        publisher
    )
    title = _clean_filename_part(title)

    if not title:
        title = _get_video_date(info)

    if publisher and title:
        return f"{publisher} - {title}"

    return publisher or title


def create_download_directory(
    base_directory,
    user_id,
):
    directory = (
        Path(base_directory)
        / str(user_id)
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory