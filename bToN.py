import os
import random
from collections import defaultdict
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from CAsh import get_chat_settings, set_chat_mode, toggle_delete_links_setting
from Reply import TXT_EDIT_PROMPT, TXT_ADMIN_ONLY, BTN_NORMAL, BTN_VOICE, BTN_DELETE_LINKS, BTN_DEVELOPER

developer_pools = defaultdict(list)
developer_color_indices = defaultdict(int)
BUTTON_STYLES = ["success", "danger", "primary"]

def get_next_developer_id(user_id: int) -> str:
    takeoff_env = os.getenv("boT_TAkeoFF", "")
    user_ids = [uid.strip() for uid in takeoff_env.split('/') if uid.strip()]
    
    if not user_ids:
        return "https://t.me"

    pool = developer_pools[user_id]
    if not pool:
        pool = list(user_ids)
        random.shuffle(pool)
        developer_pools[user_id] = pool

    selected_id = pool.pop(0)
    return f"tg://user?id={selected_id}"

def get_next_button_style(user_id: int) -> str:
    color_index = developer_color_indices[user_id]
    style = BUTTON_STYLES[color_index]
    developer_color_indices[user_id] = (color_index + 1) % len(BUTTON_STYLES)
    return style

async def is_admin(bot: Bot, message_or_query) -> bool:
    chat = message_or_query.chat if isinstance(message_or_query, Message) else message_or_query.message.chat
    user = message_or_query.from_user
    
    if chat.type == "private":
        return True
    
    if isinstance(message_or_query, Message) and message_or_query.sender_chat:
        if message_or_query.sender_chat.id == chat.id:
            return True
        return False

    if user and user.is_bot and user.username == "GroupAnonymousBot":
        return True

    if user:
        try:
            member = await bot.get_chat_member(chat.id, user.id)
            return member.status in ["creator", "administrator"]
        except Exception:
            return False

    return False

def get_settings_keyboard(current_mode: str, delete_links: bool) -> InlineKeyboardMarkup:
    normal_style = "primary" if current_mode == "normal" else "danger"
    voice_style = "primary" if current_mode == "voice" else "danger"
    delete_links_style = "primary" if delete_links else "danger"
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BTN_NORMAL, callback_data="set_mode_normal", style=normal_style),
                InlineKeyboardButton(text=BTN_VOICE, callback_data="set_mode_voice", style=voice_style)
            ],
            [
                InlineKeyboardButton(text=BTN_DELETE_LINKS, callback_data="toggle_delete_links", style=delete_links_style)
            ]
        ]
    )

def get_rotating_message_keyboard(user_id: int) -> InlineKeyboardMarkup:
    dev_url = get_next_developer_id(user_id)
    dev_style = get_next_button_style(user_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BTN_DEVELOPER, url=dev_url, style=dev_style)
            ]
        ]
    )

async def handle_edit_command(message: Message, bot: Bot):
    if not await is_admin(bot, message):
        return
    
    thread_id = message.message_thread_id or 0
    mode, delete_links = await get_chat_settings(message.chat.id, thread_id)
    await message.reply(
        TXT_EDIT_PROMPT,
        reply_markup=get_settings_keyboard(mode, delete_links)
    )

async def handle_mode_callback(query: CallbackQuery, bot: Bot):
    if not await is_admin(bot, query):
        await query.answer(TXT_ADMIN_ONLY, show_alert=True)
        return
    
    thread_id = query.message.message_thread_id or 0
    
    if query.data == "toggle_delete_links":
        new_delete_links = await toggle_delete_links_setting(query.message.chat.id, thread_id)
        current_mode, _ = await get_chat_settings(query.message.chat.id, thread_id)
        await query.message.edit_text(
            TXT_EDIT_PROMPT,
            reply_markup=get_settings_keyboard(current_mode, new_delete_links)
        )
    else:
        current_mode, current_delete_links = await get_chat_settings(query.message.chat.id, thread_id)
        requested_mode = query.data.split("_")[-1]
        if requested_mode == current_mode:
            new_mode = "voice" if current_mode == "normal" else "normal"
        else:
            new_mode = requested_mode
        
        await set_chat_mode(query.message.chat.id, thread_id, new_mode)
        await query.message.edit_text(
            TXT_EDIT_PROMPT,
            reply_markup=get_settings_keyboard(new_mode, current_delete_links)
        )

    await query.answer()
