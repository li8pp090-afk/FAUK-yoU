import asyncio
import re
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse

DOWNLOAD_ROOT = Path("downloads")

TELEGRAM_HOSTS = {
    "t.me",
    "telegram.me",
    "telegram.dog",
}


def is_telegram_url(url):
    try:
        host = (
            urlparse(url).hostname
            or ""
        ).lower().rstrip(".")
    except ValueError:
        return False

    return (
        host in TELEGRAM_HOSTS
        or any(
            host.endswith(
                "." + domain
            )
            for domain in TELEGRAM_HOSTS
        )
    )


def extract_url(text):
    if not text:
        return None

    matches = re.findall(
        r"https?://[^\s<>\u200b]+",
        text,
    )

    for url in matches:
        url = url.rstrip(
            ".,!?;:)]}>"
        )

        if not is_telegram_url(url):
            return url

    return None


def user_directory(user_id):
    path = DOWNLOAD_ROOT / str(user_id)

    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def create_task_directory(user_id):
    path = (
        user_directory(user_id)
        / f"task_{uuid.uuid4().hex}"
    )

    path.mkdir(
        parents=True,
        exist_ok=False,
    )

    return path


def cleanup_task_directory(path):
    if path and path.exists():
        shutil.rmtree(
            path,
            ignore_errors=True,
        )


def _clean_part(value):
    value = str(value or "")
    value = value.lower()

    value = re.sub(
        r"[^A-Za-z0-9_\-&\s\u0080-\uffff]",
        "",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    value = "".join(
        char.upper()
        if char in "atfgujnml"
        else char
        for char in value
    )

    return value


def _date_from_info(info):
    value = (
        info.get("upload_date")
        or info.get("release_date")
    )

    if not value:
        return None

    value = str(value)

    if (
        len(value) != 8
        or not value.isdigit()
    ):
        return None

    year = int(value[0:4])
    month = int(value[4:6])
    day = int(value[6:8])

    return f"{year}-{month}-{day}"


def build_filename(info):
    publisher = (
        info.get("uploader")
        or info.get("channel")
        or info.get("creator")
        or ""
    )

    title = info.get("title") or ""

    publisher = _clean_part(publisher)
    title = _clean_part(title)

    if not title:
        title = (
            _date_from_info(info)
            or ""
        )

    if publisher and title:
        return f"{publisher} - {title}"

    return (
        publisher
        or title
        or "download"
    )


class ScopeQueue:
    def __init__(
        self,
        max_active=3,
        max_waiting=3,
    ):
        self.max_active = max_active
        self.max_waiting = max_waiting
        self._states = {}
        self._lock = asyncio.Lock()

    async def acquire(self, scope):
        async with self._lock:
            state = self._states.setdefault(
                scope,
                {
                    "active": 0,
                    "waiting": 0,
                    "event": asyncio.Event(),
                },
            )

            if (
                state["active"]
                < self.max_active
            ):
                state["active"] += 1
                return True

            if (
                state["waiting"]
                >= self.max_waiting
            ):
                return False

            state["waiting"] += 1

        while True:
            await state["event"].wait()

            async with self._lock:
                state["event"].clear()

                if (
                    state["active"]
                    < self.max_active
                    and state["waiting"] > 0
                ):
                    state["waiting"] -= 1
                    state["active"] += 1
                    return True

    async def release(self, scope):
        async with self._lock:
            state = self._states.get(scope)

            if not state:
                return

            if state["active"] > 0:
                state["active"] -= 1

            if state["waiting"] > 0:
                state["event"].set()

            elif state["active"] == 0:
                self._states.pop(
                    scope,
                    None,
                )


QUEUE = ScopeQueue()