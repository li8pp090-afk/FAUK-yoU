import asyncio
import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle, ChatType
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaDocument,
    Message,
    ReactionTypeEmoji,
)

from bToN import DeveloperButtonRotator, UserReactionManager, get_edit_keyboard
from CAsh import get_cached_file, get_mode, init_db, save_cached_file, set_mode
from NAMe import DownloadQueueManager, generate_file_name, is_url
from Reply import (
    BTN_NORMAL_LABEL,
    BTN_VOICE_LABEL,
    CMD_BOT,
    CMD_EDIT,
    DEV_BUTTON_NAMES,
    REACTION_DELAYS,
    REACTION_EMOJIS,
    TXT_DOWNLOAD_FAILED,
    TXT_EDIT_MENU,
    TXT_NOT_ALLOWED,
    TXT_START_DOWNLOAD,
    TXT_TAKEOFF,
    USER_BOT_RESPONSES,
)
from yTFMe import execute_media_download

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BOT_TAKEOFF = os.environ.get("boT_TAkeoFF", "")

queue_manager = DownloadQueueManager(asyncio=asyncio, max_concurrent=3, max_waiting=3)
user_rotation_state = {}
user_typing_pattern_state = {}
reaction_manager = UserReactionManager(emojis=REACTION_EMOJIS, delays=REACTION_DELAYS)
dev_rotator = DeveloperButtonRotator(dev_names=DEV_BUTTON_NAMES)


def get_context_key(message: Message) -> str:
    if message.chat.type == ChatType.PRIVATE:
        return f"user_{message.from_user.id}"

    thread_id = getattr(message, "message_thread_id", None)
    if thread_id:
        return f"thread_{message.chat.id}_{thread_id}"

    return f"chat_{message.chat.id}"


def get_context_key_from_cb(cb: CallbackQuery) -> str:
    if cb.message.chat.type == ChatType.PRIVATE:
        return f"user_{cb.from_user.id}"

    thread_id = getattr(cb.message, "message_thread_id", None)
    if thread_id:
        return f"thread_{cb.message.chat.id}_{thread_id}"

    return f"chat_{cb.message.chat.id}"


async def trigger_message_reaction(bot_inst: Bot, chat_id: int, message_id: int, user_id: int):
    try:
        delay = reaction_manager.get_next_delay(user_id)
        await asyncio.sleep(delay)
        emoji = reaction_manager.get_next_emoji(user_id)
        await bot_inst.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)]
        )
    except Exception:
        pass


async def send_animated_text(
    message: Message,
    full_text: str,
    final_reply_markup=None,
    bot_inst: Bot = None
):
    user_id = message.from_user.id
    lines = full_text.split('\n')
    current_lines = []

    pattern_toggle = user_typing_pattern_state.get(user_id, True)
    sent_msg = None

    for line in lines:
        words = line.split()
        if not words:
            current_lines.append("")
            continue

        line_accum = []
        word_idx = 0

        while word_idx < len(words):
            if pattern_toggle:
                step_sizes = [2, 4]
            else:
                step_sizes = [3, 6]

            pattern_toggle = not pattern_toggle

            for count in step_sizes:
                if word_idx >= len(words):
                    break

                chunk = words[word_idx:word_idx + count]
                word_idx += count
                line_accum.extend(chunk)

                current_displayed_line = " ".join(line_accum)
                active_text = "\n".join(current_lines + [current_displayed_line])

                if sent_msg is None:
                    sent_msg = await message.reply(active_text)
                    if bot_inst:
                        asyncio.create_task(
                            trigger_message_reaction(bot_inst, sent_msg.chat.id, sent_msg.message_id, user_id)
                        )
                else:
                    try:
                        await sent_msg.edit_text(active_text)
                    except Exception:
                        pass

                await asyncio.sleep(0.3)

        current_lines.append(" ".join(line_accum))

    user_typing_pattern_state[user_id] = pattern_toggle

    if sent_msg and final_reply_markup:
        try:
            await sent_msg.edit_reply_markup(reply_markup=final_reply_markup)
        except Exception:
            pass


async def send_takeoff_message(bot_inst: Bot):
    if not BOT_TAKEOFF:
        return

    targets = [t.strip() for t in BOT_TAKEOFF.split('/') if t.strip()]
    for target in targets:
        try:
            target_id = int(target)
            reply_markup = dev_rotator.build_dev_keyboard(
                InlineKeyboardMarkup,
                InlineKeyboardButton,
                ButtonStyle,
                BOT_TAKEOFF
            )
            sent_msg = await bot_inst.send_message(
                chat_id=target_id,
                text=TXT_TAKEOFF,
                reply_markup=reply_markup
            )
            if sent_msg:
                asyncio.create_task(
                    trigger_message_reaction(bot_inst, sent_msg.chat.id, sent_msg.message_id, target_id)
                )
        except Exception:
            pass


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def is_admin(bot_inst: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot_inst.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False


@dp.message(F.text.lower() == CMD_EDIT.lower())
async def handle_edit_command(message: Message, bot_inst: Bot):
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if not await is_admin(bot_inst, message.chat.id, message.from_user.id):
            return

    key = get_context_key(message)
    mode = get_mode(sqlite3, key)
    keyboard = get_edit_keyboard(
        InlineKeyboardMarkup,
        InlineKeyboardButton,
        ButtonStyle,
        BTN_VOICE_LABEL,
        BTN_NORMAL_LABEL,
        mode
    )

    await send_animated_text(
        message=message,
        full_text=TXT_EDIT_MENU,
        final_reply_markup=keyboard,
        bot_inst=bot_inst
    )


@dp.callback_query(F.data.in_({"toggle_voice", "toggle_normal"}))
async def handle_edit_callback(cb: CallbackQuery, bot_inst: Bot):
    if cb.message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if not await is_admin(bot_inst, cb.message.chat.id, cb.from_user.id):
            await cb.answer(TXT_NOT_ALLOWED, show_alert=True)
            return

    key = get_context_key_from_cb(cb)
    current_mode = get_mode(sqlite3, key)
    new_mode = "normal" if current_mode == "voice" else "voice"

    set_mode(sqlite3, key, new_mode)
    new_keyboard = get_edit_keyboard(
        InlineKeyboardMarkup,
        InlineKeyboardButton,
        ButtonStyle,
        BTN_VOICE_LABEL,
        BTN_NORMAL_LABEL,
        new_mode
    )

    try:
        await cb.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception:
        pass

    await cb.answer()


async def process_media_request(message: Message, text: str):
    key = get_context_key(message)
    if not queue_manager.can_enqueue(key):
        return

    if await queue_manager.acquire(key):
        try:
            await execute_media_download(
                os, json, shutil, datetime, subprocess, asyncio, sqlite3,
                FSInputFile, InputMediaDocument, message,
                get_mode, get_cached_file, save_cached_file, generate_file_name,
                TXT_START_DOWNLOAD, TXT_DOWNLOAD_FAILED, message, text, key, re,
                dev_rotator, InlineKeyboardMarkup, InlineKeyboardButton, ButtonStyle,
                BOT_TAKEOFF
            )
        finally:
            queue_manager.release(key)


def get_next_response(user_id: int) -> str:
    current_index = user_rotation_state.get(user_id, 0)
    response_text = USER_BOT_RESPONSES[current_index]
    user_rotation_state[user_id] = (current_index + 1) % len(USER_BOT_RESPONSES)
    return response_text


@dp.message(F.chat.type == ChatType.PRIVATE, ~F.text.startswith("/"))
async def handle_private_chat(message: Message, bot_inst: Bot):
    if not message.text:
        return

    text = message.text.strip()
    if is_url(re, text):
        await process_media_request(message, text)
    else:
        reply_markup = dev_rotator.build_dev_keyboard(
            InlineKeyboardMarkup,
            InlineKeyboardButton,
            ButtonStyle,
            BOT_TAKEOFF
        )
        response_text = get_next_response(message.from_user.id)
        await send_animated_text(
            message=message,
            full_text=response_text,
            final_reply_markup=reply_markup,
            bot_inst=bot_inst
        )


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def handle_group_chat(message: Message, bot_inst: Bot):
    if not message.text:
        return

    text = message.text.strip()
    if is_url(re, text):
        await process_media_request(message, text)
    elif text.lower() == CMD_BOT.lower():
        reply_markup = dev_rotator.build_dev_keyboard(
            InlineKeyboardMarkup,
            InlineKeyboardButton,
            ButtonStyle,
            BOT_TAKEOFF
        )
        response_text = get_next_response(message.from_user.id)
        await send_animated_text(
            message=message,
            full_text=response_text,
            final_reply_markup=reply_markup,
            bot_inst=bot_inst
        )


async def main():
    init_db(sqlite3)
    await send_takeoff_message(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
