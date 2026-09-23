import os
import asyncio
from aiogram import Bot, Router, F
from aiogram.types import Message, FSInputFile

from yTFMe import convert_to_opus_ogg
from Reply import CMD_EXTRACT_AUDIO, TXT_AUDIO_EXTRACTION_FAILED
from CAsh import get_extracted_voice_id, save_extracted_voice_id

router = Router()

async def has_audio_stream(file_path: str) -> bool:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    stdout, _ = await proc.communicate()
    return bool(stdout.decode().strip())

@router.message(F.text == CMD_EXTRACT_AUDIO)
async def process_extract_audio(message: Message, bot: Bot):
    if not message.reply_to_message:
        return

    reply = message.reply_to_message
    
    media = reply.video or reply.document or reply.audio or reply.video_note
    if not media:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    thread_id = message.message_thread_id if getattr(message, "is_topic_message", False) else None
    input_file_id = media.file_id

    cached_voice_id = await get_extracted_voice_id(input_file_id)
    if cached_voice_id:
        await bot.send_voice(
            chat_id=chat_id,
            message_thread_id=thread_id,
            voice=cached_voice_id,
            reply_to_message_id=reply.message_id
        )
        return

    file_info = await bot.get_file(input_file_id)
    
    download_path = f"temp_extract_{user_id}_{input_file_id[:10]}"
    final_opus_path = None

    try:
        await bot.download_file(file_info.file_path, download_path)
        
        contains_audio = await has_audio_stream(download_path)
        if not contains_audio:
            await message.reply(TXT_AUDIO_EXTRACTION_FAILED)
            return

        final_opus_path = await convert_to_opus_ogg(download_path, os.getcwd())
        
        if final_opus_path and os.path.exists(final_opus_path):
            sent_msg = await bot.send_voice(
                chat_id=chat_id,
                message_thread_id=thread_id,
                voice=FSInputFile(final_opus_path),
                reply_to_message_id=reply.message_id
            )
            if sent_msg and sent_msg.voice:
                await save_extracted_voice_id(input_file_id, sent_msg.voice.file_id)
        else:
            await message.reply(TXT_AUDIO_EXTRACTION_FAILED)

    except Exception:
        await message.reply(TXT_AUDIO_EXTRACTION_FAILED)
    finally:
        for path in [download_path, final_opus_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
