from aiogram import Router
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

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

    value = ids[ID_INDEX]

    ID_INDEX = (
        ID_INDEX + 1
    ) % len(ids)

    return value


def get_next_color():
    global COLOR_INDEX

    value = COLORS[COLOR_INDEX]

    COLOR_INDEX = (
        COLOR_INDEX + 1
    ) % len(COLORS)

    return value


def get_markup():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=Reply.DEVELOPER_BUTTON,
                    callback_data="developer",
                    style=get_next_color()
                )
            ]
        ]
    )


@router.callback_query(
    lambda callback:
    callback.data == "developer"
)
async def developer_callback(
    callback: CallbackQuery
):
    developer_id = get_next_id()

    if developer_id is None:
        await callback.answer()
        return

    await callback.answer(
        str(developer_id),
        show_alert=True
    )