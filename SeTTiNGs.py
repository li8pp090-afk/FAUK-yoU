import hashlib
import re

from urllib.parse import urlparse


UPPER_EXCEPTIONS = set(
    "ATFGUJNML"
)

IGNORED_HOSTS = {
    "t.me",
    "telegram.me",
    "www.youtube.com",
    "youtube.com",
    "youtu.be",
    "m.youtube.com",
}


def clean_component(
    value: str,
) -> str:
    value = re.sub(
        r'[\\/:*?"<>|]+',
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


def format_title(
    value: str,
) -> str:
    value = clean_component(
        value
    )

    result = []

    for index, char in enumerate(value):
        if (
            char.isalpha()
            and char.upper()
            in UPPER_EXCEPTIONS
        ):
            result.append(
                char.upper()
            )
        else:
            result.append(char)

    return "".join(result)


def build_filename(
    info: dict,
    actual_path,
):
    title = format_title(
        str(
            info.get("title")
            or "media"
        )
    )

    ext = actual_path.suffix

    if not ext:
        ext = ".bin"

    return f"{title}{ext}"


def is_ignored_url(
    url: str,
) -> bool:
    try:
        host = (
            urlparse(url)
            .netloc
            .lower()
            .split(":")[0]
        )
    except Exception:
        return False

    return host in IGNORED_HOSTS


def normalize_url(
    text: str,
):
    text = text.strip()

    if not text:
        return None

    match = re.search(
        r"https?://[^\s]+",
        text,
    )

    if not match:
        return None

    return match.group(0).rstrip(
        ".,!?)]}"
    )


def sha256_id(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()