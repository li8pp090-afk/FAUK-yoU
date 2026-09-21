from functools import partial

from aiogram import F
from aiogram import Dispatcher, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from Reply import (
    UNAUTHORIZED,
    VOICE_BUTTON,
    VIRTUAL_BUTTON,
    AUTO_ENABLE_BUTTON,
    VOICE_EDIT_INFO,
    VOICE_EDIT_INFO_BUTTON
)

from CAsh import (
    get_mode,
    set_mode,
    is_edit_button_owner,
    get_auto_enable,
    set_auto_enable
)


def mode_keyboard(
    current_mode,
    auto_enabled=True
):
    if current_mode == "voice":
        voice_style = "primary"
        virtual_style = "danger"
    else:
        voice_style = "danger"
        virtual_style = "primary"

    auto_style = (
        "primary"
        if auto_enabled
        else "danger"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=AUTO_ENABLE_BUTTON,
                    callback_data="auto:toggle",
                    style=auto_style
                )
            ],
            [
                InlineKeyboardButton(
                    text=VIRTUAL_BUTTON,
                    callback_data="mode:virtual",
                    style=virtual_style
                ),
                InlineKeyboardButton(
                    text=VOICE_BUTTON,
                    callback_data="mode:voice",
                    style=voice_style
                )
            ]
        ]
    )


async def is_channel_admin(
    bot: Bot,
    chat_id: int,
    user_id: int
):
    member = await bot.get_chat_member(
        chat_id,
        user_id
    )

    return member.status in {
        "creator",
        "administrator"
    }


async def mode_callback(
    callback: CallbackQuery,
    bot: Bot
):
    if callback.message is None:
        return

    if callback.message.chat.type == "channel":
        if not await is_channel_admin(
            bot,
            callback.message.chat.id,
            callback.from_user.id
        ):
            await callback.answer(
                UNAUTHORIZED,
                show_alert=True
            )
            return
    else:
        if not await is_edit_button_owner(
            callback.message.chat.id,
            callback.message.message_id,
            callback.from_user.id
        ):
            await callback.answer(
                UNAUTHORIZED,
                show_alert=True
            )
            return

    requested_mode = callback.data.split(
        ":",
        1
    )[1]

    if requested_mode not in {
        "voice",
        "virtual"
    }:
        await callback.answer()
        return

    if callback.message.chat.type == "private":
        scope_id = (
            f"private:{callback.message.chat.id}"
        )

    elif callback.message.chat.type in {
        "group",
        "supergroup"
    }:
        thread_id = (
            callback.message.message_thread_id
        )

        if thread_id:
            scope_id = (
                f"chat:{callback.message.chat.id}"
                f":topic:{thread_id}"
            )
        else:
            scope_id = (
                f"chat:{callback.message.chat.id}"
            )

    elif callback.message.chat.type == "channel":
        scope_id = (
            f"channel:{callback.message.chat.id}"
        )

    else:
        await callback.answer()
        return

    current_mode = await get_mode(
        scope_id
    )

    if requested_mode == current_mode:
        new_mode = (
            "virtual"
            if current_mode == "voice"
            else "voice"
        )
    else:
        new_mode = requested_mode

    await set_mode(
        scope_id,
        new_mode
    )

    auto_enabled = await get_auto_enable(
        callback.from_user.id
    )

    await callback.message.edit_reply_markup(
        reply_markup=mode_keyboard(
            new_mode,
            auto_enabled
        )
    )

    await callback.answer()


async def auto_enable_callback(
    callback: CallbackQuery
):
    if callback.message is None:
        return

    if not await is_edit_button_owner(
        callback.message.chat.id,
        callback.message.message_id,
        callback.from_user.id
    ):
        await callback.answer(
            UNAUTHORIZED,
            show_alert=True
        )
        return

    current = await get_auto_enable(
        callback.from_user.id
    )

    new_value = not current

    await set_auto_enable(
        callback.from_user.id,
        new_value
    )

    current_mode = await get_mode(
        get_scope_id_from_callback(
            callback
        )
    )

    await callback.message.edit_reply_markup(
        reply_markup=mode_keyboard(
            current_mode,
            new_value
        )
    )

    await callback.answer()


def get_scope_id_from_callback(
    callback: CallbackQuery
):
    message = callback.message

    if message.chat.type == "private":
        return (
            f"private:{message.chat.id}"
        )

    if message.chat.type in {
        "group",
        "supergroup"
    }:
        thread_id = message.message_thread_id

        if thread_id:
            return (
                f"chat:{message.chat.id}"
                f":topic:{thread_id}"
            )

        return (
            f"chat:{message.chat.id}"
        )

    if message.chat.type == "channel":
        return (
            f"channel:{message.chat.id}"
        )

    return (
        f"chat:{message.chat.id}"
    )


async def voice_edit_info_callback(
    callback: CallbackQuery
):
    await callback.answer(
        VOICE_EDIT_INFO,
        show_alert=True
    )


def register_button_handlers(
    dp: Dispatcher,
    bot: Bot
):
    dp.callback_query.register(
        partial(
            mode_callback,
            bot=bot
        ),
        F.data.startswith("mode:")
    )

    dp.callback_query.register(
        auto_enable_callback,
        F.data == "auto:toggle"
    )

    dp.callback_query.register(
        voice_edit_info_callback,
        F.data == "voice_edit_info"
    )
