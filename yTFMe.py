import asyncio
import os
import tempfile

async def download_with_ytdlp(url: str, tmp_dir: str, mode: str) -> bool:
    output_template = os.path.join(
        tmp_dir, 
        "%(uploader,channel,creator)s - %(title)s.%(ext)s"
    )

    if mode == "voice":
        format_option = "bestaudio/best"
    else:
        format_option = "bestvideo+bestaudio/best"

    yt_dlp_cmd = [
        "yt-dlp",
        "--yes-playlist",
        "-f", format_option,
        "-o", output_template,
        "--restrict-filenames",
        url
    ]

    proc_download = await asyncio.create_subprocess_exec(
        *yt_dlp_cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc_download.wait()
    return proc_download.returncode == 0

async def convert_to_opus_ogg(downloaded_file: str, tmp_dir: str) -> str:
    ogg_path = tempfile.mktemp(suffix=".ogg", dir=tmp_dir)

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i", downloaded_file,
        "-c:a", "libopus",
        "-f", "ogg",
        ogg_path
    ]

    proc_ffmpeg = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc_ffmpeg.wait()

    if os.path.exists(ogg_path):
        return ogg_path
    return None

async def merge_best_quality(downloaded_file: str, tmp_dir: str) -> str:
    output_path = tempfile.mktemp(dir=tmp_dir)

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i", downloaded_file,
        "-c", "copy",
        output_path
    ]

    proc_ffmpeg = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc_ffmpeg.wait()

    if os.path.exists(output_path):
        return output_path
    return downloaded_file
