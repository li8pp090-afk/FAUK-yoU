import asyncio
import os
import re
import tempfile
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, CallbackQuery, InputMediaDocument

from CAsh import init_db, get_cached_file_id, save_file_id, get_chat_mode
from yTFMe import download_with_ytdlp, convert_to_opus_ogg, merge_best_quality
from NAMe import process_downloaded_filenames
from bToN import handle_edit_command, handle_mode_callback, get_rotating_message_keyboard
from Reply import CMD_EDIT, TRIGGER_BOT_KEYWORD, TXT_START_DOWNLOAD, TXT_DOWNLOAD_FAILED, TXT_TAKEOFF, ROTATING_MESSAGES

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class UserStateManager:
    def __init__(self):
        self.semaphores = defaultdict(lambda: asyncio.Semaphore(3))
        self.active_and_queued_counts = defaultdict(int)
        self.locks = defaultdict(asyncio.Lock)
        self.user_message_indices = defaultdict(int)

    def get_user_semaphore(self, user_id: int) -> asyncio.Semaphore:
        return self.semaphores[user_id]

    async def try_enqueue(self, user_id: int) -> bool:
        async with self.locks[user_id]:
            if self.active_and_queued_counts[user_id] >= 6:
                return False
            self.active_and_queued_counts[user_id] += 1
            return True

    async def release(self, user_id: int):
        async with self.locks[user_id]:
            if self.active_and_queued_counts[user_id] > 0:
                self.active_and_queued_counts[user_id] -= 1

    async def get_next_rotating_message(self, user_id: int) -> str:
        async with self.locks[user_id]:
            index = self.user_message_indices[user_id]
            msg = ROTATING_MESSAGES[index]
            self.user_message_indices[user_id] = (index + 1) % len(ROTATING_MESSAGES)
            return msg

user_manager = UserStateManager()

TELEGRAM_URL_PATTERN = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.dog)/', re.IGNORECASE)
URL_PATTERN = re.compile(r'https?://[^\s]+', re.IGNORECASE)

async def send_takeoff_message():
    takeoff_env = os.getenv("boT_TAkeoFF")
    if not takeoff_env:
        return
    
    user_ids = [uid.strip() for uid in takeoff_env.split('/') if uid.strip()]
    for user_id_str in user_ids:
        try:
            uid = int(user_id_str)
            keyboard = get_rotating_message_keyboard(uid)
            await bot.send_message(chat_id=uid, text=TXT_TAKEOFF, reply_markup=keyboard)
        except Exception:
            pass

@dp.message(F.text == CMD_EDIT)
async def on_edit_command(message: Message):
    await handle_edit_command(message, bot)

@dp.callback_query(F.data.startswith("set_mode_"))
async def on_mode_callback(query: CallbackQuery):
    await handle_mode_callback(query, bot)

async def process_audio_url(message: Message, url: str):
    user_id = message.from_user.id

    if not await user_manager.try_enqueue(user_id):
        return

    status_msg = None
    tmp_dir = None
    downloaded_files = []
    processed_files = []

    try:
        user_semaphore = user_manager.get_user_semaphore(user_id)
        async with user_semaphore:
            thread_id = message.message_thread_id or 0
            mode = await get_chat_mode(message.chat.id, thread_id)

            full_cache_key = f"{url}_{mode}"
            cached_file_id = await get_cached_file_id(full_cache_key)
            
            if cached_file_id:
                file_ids = cached_file_id.split(",")
                if mode == "voice":
                    for fid in file_ids:
                        await message.reply_voice(voice=fid)
                else:
                    for i in range(0, len(file_ids), 10):
                        chunk = file_ids[i:i+10]
                        media_group = [InputMediaDocument(media=fid) for fid in chunk]
                        await message.reply_media_group(media=media_group)
                return

            status_msg = await message.reply(TXT_START_DOWNLOAD)

            tmp_dir = tempfile.mkdtemp()
            
            success = await download_with_ytdlp(url, tmp_dir, mode)
            if not success:
                if status_msg:
                    await status_msg.edit_text(TXT_DOWNLOAD_FAILED)
                return

            downloaded_files = process_downloaded_filenames(tmp_dir)

            if not downloaded_files:
                if status_msg:
                    await status_msg.edit_text(TXT_DOWNLOAD_FAILED)
                return

            if status_msg:
                try:
                    await status_msg.delete()
                    status_msg = None
                except Exception:
                    pass

            saved_file_ids = []

            if mode == "voice":
                for downloaded_file in downloaded_files:
                    processed_path = await convert_to_opus_ogg(downloaded_file, tmp_dir)
                    if processed_path and os.path.exists(processed_path):
                        processed_files.append(processed_path)
                        sent_msg = await message.reply_voice(voice=FSInputFile(processed_path))
                        if sent_msg and sent_msg.voice:
                            saved_file_ids.append(sent_msg.voice.file_id)
            else:
                for downloaded_file in downloaded_files:
                    processed_path = await merge_best_quality(downloaded_file, tmp_dir)
                    if processed_path and os.path.exists(processed_path):
                        processed_files.append(processed_path)
                    else:
                        processed_files.append(downloaded_file)

                for i in range(0, len(processed_files), 10):
                    chunk = processed_files[i:i+10]
                    media_group = [InputMediaDocument(media=FSInputFile(f)) for f in chunk]
                    
                    sent_messages = await message.reply_media_group(media=media_group)
                    for msg in sent_messages:
                        if msg.document:
                            saved_file_ids.append(msg.document.file_id)

            if saved_file_ids:
                await save_file_id(full_cache_key, ",".join(saved_file_ids))

    except Exception:
        if status_msg:
            try:
                await status_msg.edit_text(TXT_DOWNLOAD_FAILED)
            except Exception:
                pass
    finally:
        for f in processed_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

        for f in downloaded_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

        if tmp_dir and os.path.exists(tmp_dir):
            try:
                for root, dirs, files in os.walk(tmp_dir, topdown=False):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except Exception:
                            pass
                    for name in dirs:
                        try:
                            os.rmdir(os.path.join(root, name))
                        except Exception:
                            pass
                os.rmdir(tmp_dir)
            except Exception:
                pass

        await user_manager.release(user_id)

@dp.message(F.text)
async def handle_message(message: Message):
    text = message.text.strip()
    
    if text == CMD_EDIT:
        return

    if TELEGRAM_URL_PATTERN.search(text):
        return

    match = URL_PATTERN.search(text)
    if match:
        url = match.group(0)
        asyncio.create_task(process_audio_url(message, url))
        return

    chat_type = message.chat.type
    if chat_type in ["group", "supergroup"]:
        if text != TRIGGER_BOT_KEYWORD:
            return

    user_id = message.from_user.id
    reply_text = await user_manager.get_next_rotating_message(user_id)
    keyboard = get_rotating_message_keyboard(user_id)
    await message.reply(reply_text, reply_markup=keyboard)

async def main():
    await init_db()
    await send_takeoff_message()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
