import re

import bUTToN
import CAsh
import Reply

from yTFMe import make_job_id, ensure_workers


URL_RE = re.compile(
    r"https?://\S+|www\.\S+",
    re.I
)


class App:
    def __init__(
        self,
        bot,
        dp,
        db,
        takeoff_ids=None
    ):
        self.bot = bot
        self.dp = dp
        self.db = db
        self.takeoff_ids = takeoff_ids or []

    async def get_mode(self, user_id):
        return await CAsh.get_mode(
            self.db,
            user_id
        )

    async def set_mode(self, user_id, mode):
        await CAsh.set_mode(
            self.db,
            user_id,
            mode
        )

    async def pop_job(self, user_id):
        return await CAsh.pop_job(
            self.db,
            user_id
        )

    async def get_cached_file(self, mode, url):
        return await CAsh.get_cached_file(
            self.db,
            mode,
            url
        )

    async def set_cached_file(
        self,
        mode,
        url,
        file_id
    ):
        await CAsh.set_cached_file(
            self.db,
            mode,
            url,
            file_id
        )

    async def delete_cached_file(
        self,
        mode,
        url
    ):
        await CAsh.delete_cached_file(
            self.db,
            mode,
            url
        )

    async def send_failed(self, chat_id):
        await self.bot.send_message(
            chat_id,
            Reply.DOWNLOAD_FAILED
        )

    def start_workers(self, user_id):
        ensure_workers(
            self.bot,
            user_id,
            self.pop_job,
            self.get_cached_file,
            self.set_cached_file,
            self.delete_cached_file,
            self.send_failed
        )

    async def reply_normal(self, message):
        index = await CAsh.get_reply_index(
            self.db,
            message.from_user.id,
            len(Reply.NORMAL_REPLIES)
        )

        keyboard = bUTToN.takeoff_keyboard(
            self.takeoff_ids
        )

        await message.answer(
            Reply.NORMAL_REPLIES[index],
            reply_markup=keyboard
        )

    async def cleanup_queues(self):
        await CAsh.clear_all_queues(
            self.db
        )

    async def cleanup_files(self):
        from yTFMe import cleanup_old_files
        await cleanup_old_files()

    def register_buttons(self):
        bUTToN.register(
            self.dp,
            self.get_mode,
            self.set_mode
        )

    def register_messages(self):
        from aiogram.types import Message

        @self.dp.message()
        async def handle_message(
            message: Message
        ):
            if not message.text:
                return

            text = message.text.strip()

            if text == Reply.EDIT_TRIGGER:
                return

            if not URL_RE.search(text):
                await self.reply_normal(message)
                return

            user_id = message.from_user.id
            mode = await self.get_mode(user_id)

            job = {
                "user_id": user_id,
                "chat_id": message.chat.id,
                "url": text,
                "mode": mode,
                "job_id": make_job_id(
                    user_id,
                    message.message_id
                )
            }

            accepted = await CAsh.push_job(
                self.db,
                user_id,
                job
            )

            if not accepted:
                return

            await message.answer(
                Reply.DOWNLOAD_STARTED
            )

            self.start_workers(user_id)

    def register(self):
        self.register_buttons()
        self.register_messages()