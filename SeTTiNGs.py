import re


def clean_name(value):
    if not value:
        return "unknown"

    value = str(value).strip()

    value = re.sub(
        r"[^\w\s\u0600-\u06FF]",
        "",
        value,
        flags=re.UNICODE
    )

    value = re.sub(r"\s+", " ", value).strip()

    result = []

    for char in value:
        if char.isascii() and char.isalpha():
            if char.upper() in "ATFGUJNML":
                result.append(char.upper())
            else:
                result.append(char.lower())
        else:
            result.append(char)

    value = "".join(result)

    return value or "unknown"


def build_filename(info, ext):
    publisher = clean_name(
        info.get("uploader")
        or info.get("channel")
        or info.get("creator")
        or ""
    )

    title = clean_name(
        info.get("title")
        or "video"
    )

    if publisher and publisher != "unknown":
        name = f"{publisher} - {title}"
    else:
        name = title

    return f"{name}.{ext}"