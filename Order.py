import os


def get_bot_token():
    return os.getenv(
        "BOT_TOKEN"
    )


def get_boot_takeoff():
    return os.getenv(
        "boT_TAkeoFF",
        ""
    )


def get_startup_ids():
    return [
        item.strip()
        for item in get_boot_takeoff().split("/")
        if item.strip().isdigit()
    ]


def get_max_active():
    return 3


def get_max_queue():
    return 3