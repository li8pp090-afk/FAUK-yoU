import re


KEEP_UPPER = set(
    "atfgujnml"
)


def clean_name(value):
    value = value or ""

    result = []

    for char in value:
        if char == "_":
            result.append(char)
            continue

        if char.isspace():
            result.append(" ")
            continue

        if char.isalpha():
            if char.isascii():
                char = char.lower()

                if char in KEEP_UPPER:
                    char = char.upper()

            result.append(char)

    return re.sub(
        r" +",
        " ",
        "".join(result)
    ).strip()


def make_filename(info):
    publisher = clean_name(
        info.get("uploader")
        or info.get("channel")
        or ""
    )

    title = clean_name(
        info.get("title")
        or ""
    )

    if publisher and title:
        return (
            f"{publisher} - {title}"
        )

    return (
        publisher
        or title
        or "download"
    )