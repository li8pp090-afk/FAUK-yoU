import asyncio
import shutil
import tempfile
from pathlib import Path

import yt_dlp


def get_entry_url(entry):
    return (
        entry.get("webpage_url")
        or entry.get("original_url")
        or entry.get("url")
    )


async def create_temp_directory():
    return await asyncio.to_thread(
        tempfile.mkdtemp
    )


async def merge_with_ffmpeg(
    video,
    audio,
    output
):
    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg is not available"
        )

    process = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-y",
        "-i", str(video),
        "-i", str(audio),
        "-c", "copy",
        str(output),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE
    )

    stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            stderr.decode(
                errors="replace"
            )
        )


async def download(
    url,
    directory
):
    def run():
        output_template = str(
            Path(directory)
            / "%(id)s.%(ext)s"
        )

        options = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestvideo+bestaudio/best",
            "outtmpl": output_template,
            "restrictfilenames": False,
            "windowsfilenames": False
        }

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:
            info = ydl.extract_info(
                url,
                download=True
            )

            if not info:
                return []

            entries = info.get("entries")

            if entries:
                entries = [
                    entry
                    for entry in entries
                    if entry
                ]
            else:
                entries = [info]

            files = [
                path
                for path in Path(
                    directory
                ).iterdir()
                if path.is_file()
            ]

            result = []

            for entry in entries:
                entry_id = entry.get("id")

                if not entry_id:
                    continue

                candidates = [
                    path
                    for path in files
                    if entry_id in path.stem
                ]

                if not candidates:
                    continue

                path = max(
                    candidates,
                    key=lambda item:
                    item.stat().st_size
                )

                entry[
                    "_downloaded_path"
                ] = path

                result.append(
                    entry
                )

            return result

    return await asyncio.to_thread(
        run
    )


async def cleanup(directory):
    def remove():
        path = Path(directory)

        if path.exists():
            shutil.rmtree(
                path,
                ignore_errors=True
            )

    await asyncio.to_thread(
        remove
    )