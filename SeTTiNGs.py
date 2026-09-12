import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

UPPER_EXCEPTIONS = set("ATFGUJNML")

IGNORED_HOSTS = {
    "t.me",
    "telegram.me",
    "telegram.dog",
    "www.t.me",
    "www.telegram.me",
    "www.telegram.dog",
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def clean_component(value: str) -> str:
    value = (value or "").strip()

    if not value:
        return ""

    value = re.sub(
        r"[^\w\s]",
        "",
        value,
        flags=re.UNICODE,
    )

    value = re.sub(
        r"[\r\n\t]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    chars = []

    for ch in value:
        if ch.isascii() and ch.isalpha():
            if ch.upper() in UPPER_EXCEPTIONS:
                chars.append(ch.upper())
            else:
                chars.append(ch.lower())
        else:
            chars.append(ch)

    return "".join(chars)


def build_filename(
    info: dict,
    actual_path: Path,
) -> str:
    publisher_raw = (
        info.get("channel")
        or info.get("uploader")
        or info.get("creator")
        or ""
    )

    publisher = clean_component(
        publisher_raw,
    )

    title = clean_component(
        info.get("title") or "",
    )

    if publisher and title:
        stem = f"{publisher} - {title}"
    else:
        stem = (
            publisher
            or title
            or clean_component(actual_path.stem)
            or "file"
        )

    return f"{stem}{actual_path.suffix}"


def is_ignored_url(url: str) -> bool:
    try:
        host = (
            urlparse(url).hostname
            or ""
        ).lower()

        return (
            host in IGNORED_HOSTS
            or host.endswith(".telegram.org")
            or host.endswith(".youtube.com")
        )
    except Exception:
        return False


def normalize_url(
    text: str,
) -> str | None:
    match = re.search(
        r"https?://\S+",
        text or "",
    )

    if not match:
        return None

    return match.group(0).rstrip(
        ".,!?)]}"
    )


def sha256_id(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8"),
    ).hexdigest()