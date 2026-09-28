from aiogram import Router
from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import Order
import Reply


router = Router()

ID_INDEX = 0
COLOR_INDEX = 0

COLORS = [
    ButtonStyle.SUCCESS,
    ButtonStyle.DANGER,
    ButtonStyle.PRIMARY
]


def get_next_id():
    global ID_INDEX

    ids = Order.get_startup_ids()

    if not ids:
        return None

    developer_id = ids[ID_INDEX]

    ID_INDEX = (
        ID_INDEX + 1
    ) % len(ids)

    return developer_id


def get_next_color():
    global COLOR_INDEX

    color = COLORS[COLOR_INDEX]

    COLOR_INDEX = (
        COLOR_INDEX + 1
    ) % len(COLORS)

    return color


def get_markup():
    developer_id = get_next_id()

    if not developer_id:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=Reply.DEVELOPER_BUTTON,
                    url=f"tg://user?id={developer_id}",
                    style=get_next_color()
                )
            ]
        ]
    )