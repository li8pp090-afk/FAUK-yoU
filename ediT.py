import re
import os
import asyncio
from aiogram import Bot, Router, F
from aiogram.types import Message, FSInputFile

from yTFMe import convert_to_opus_ogg
from Reply import CMD_AUDIO_EDIT, TXT_AUDIO_EDIT_PROMPT, TXT_AUDIO_DURATION_TOO_LONG

router = Router()

user_edit_states = {}

def parse_time_segment(time_str: str) -> float | None:
    time_str = time_str.strip()
    
    match_hours = re.match(r'^(\d+)\.(\d+):(\d+)(?:\.(\d+))?$', time_str)
    if match_hours:
        hours = int(match_hours.group(1))
        minutes = int(match_hours.group(2))
        seconds = int(match_hours.group(3))
        sub_sec_raw = match_hours.group(4)
        
        if minutes >= 60 or seconds >= 60:
            return None
            
        sub_seconds = 0.0
        if sub_sec_raw:
            val = int(sub_sec_raw)
            if val >= 60:
                return None
            sub_seconds = val / 60.0
            
        return hours * 3600 + minutes * 60 + seconds + sub_seconds

    match_minutes = re.match(r'^(\d+):(\d+)(?:\.(\d+))?$', time_str)
    if match_minutes:
        minutes = int(match_minutes.group(1))
        seconds = int(match_minutes.group(2))
        sub_sec_raw = match_minutes.group(3)
        
        if seconds >= 60:
            return None
            
        sub_seconds = 0.0
        if sub_sec_raw:
            val = int(sub_sec_raw)
            if val >= 60:
                return None
            sub_seconds = val / 60.0
            
        return minutes * 60 + seconds + sub_seconds

    match_seconds_only = re.match(r'^(\d+)(?:\.(\d+))?$', time_str)
    if match_seconds_only:
        seconds = int(match_seconds_only.group(1))
        sub_sec_raw = match_seconds_only.group(2)
        
        sub_seconds = 0.0
        if sub_sec_raw:
            val = int(sub_sec_raw)
            if val >= 60:
                return None
            sub_seconds = val / 60.0
            
        return seconds + sub_seconds

    return None

def parse_time_range(text: str) -> tuple[float, float] | None:
    text = text.strip()
    pattern = r'^\s*(\S+)\s+(?:[-_/\s])\s+(\S+)\s*$'
    match = re.match(pattern, text)
    if not match:
        return None
    
    start_raw = match.group(1)
    end_raw = match.group(2)
    
    start_sec = parse_time_segment(start_raw)
    end_sec = parse_time_segment(end_raw)
    
    if start_sec is None or end_sec is None:
        return None
    
    if start_sec >= end_sec:
        return None
        
    return start_sec, end_sec

async def get_audio_duration(file_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except Exception:
        return 0.0

async def trim_audio_with_ffmpeg(input_path: str, output_path: str, start_sec: float, duration_sec: float) -> bool:
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{start_sec:.3f}",
        "-t", f"{duration_sec:.3f}",
        "-i", input_path,
        "-c", "copy",
        output_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()
    return proc.returncode == 0 and os.path.exists(output_path)

@router.message(F.text == CMD_AUDIO_EDIT)
async def start_edit_mode(message: Message, bot: Bot):
    if not message.reply_to_message:
        return

    reply = message.reply_to_message
    voice = reply.voice or reply.audio
    if not voice:
        return

    user_id = message.from_user.id
    
    user_edit_states[user_id] = {
        "file_id": voice.file_id,
        "chat_id": message.chat.id,
        "reply_to_msg_id": reply.message_id,
        "message_thread_id": message.message_thread_id if getattr(message, "is_topic_message", False) else None,
        "attempts": 0
    }

    await message.reply(TXT_AUDIO_EDIT_PROMPT)

@router.message(F.text)
async def process_edit_input(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id not in user_edit_states:
        return

    state = user_edit_states[user_id]
    time_range = parse_time_range(message.text)

    if not time_range:
        state["attempts"] += 1
        await message.reply(TXT_AUDIO_DURATION_TOO_LONG)
        if state["attempts"] >= 2:
            user_edit_states.pop(user_id, None)
        return

    start_sec, end_sec = time_range
    file_id = state["file_id"]
    chat_id = state["chat_id"]
    reply_to_msg_id = state["reply_to_msg_id"]
    thread_id = state["message_thread_id"]

    file_info = await bot.get_file(file_id)
    
    download_path = f"temp_edit_{user_id}_{file_id[:10]}.ogg"
    trimmed_path = f"temp_trimmed_{user_id}_{file_id[:10]}.ogg"
    final_opus_path = None

    try:
        await bot.download_file(file_info.file_path, download_path)
        total_duration = await get_audio_duration(download_path)
        
        if end_sec > total_duration:
            state["attempts"] += 1
            await message.reply(TXT_AUDIO_DURATION_TOO_LONG)
            if state["attempts"] >= 2:
                user_edit_states.pop(user_id, None)
            return

        duration_to_cut = end_sec - start_sec
        success = await trim_audio_with_ffmpeg(download_path, trimmed_path, start_sec, duration_to_cut)
        
        if success:
            final_opus_path = await convert_to_opus_ogg(trimmed_path, os.getcwd())
            target_path = final_opus_path if final_opus_path else trimmed_path
            
            await bot.send_voice(
                chat_id=chat_id,
                message_thread_id=thread_id,
                voice=FSInputFile(target_path),
                reply_to_message_id=reply_to_msg_id
            )
            user_edit_states.pop(user_id, None)

    except Exception:
        user_edit_states.pop(user_id, None)
    finally:
        for path in [download_path, trimmed_path, final_opus_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
