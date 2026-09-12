import asyncio
from pathlib import Path

import yt_dlp


def ytdlp_options(
    workdir: str,
    mode: str,
) -> dict:
    options = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "paths": {
            "home": workdir,
        },
    }

    if mode == "voice":
        options["format"] = "bestaudio/best"
    else:
        options["format"] = "bestvideo+bestaudio/best"

    return options


def download_with_ytdlp(
    url: str,
    mode: str,
    workdir: str,
):
    options = ytdlp_options(
        workdir,
        mode,
    )

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=True,
        )

        prepared = Path(
            ydl.prepare_filename(info),
        )

        if prepared.exists():
            return prepared, info

        files = [
            path
            for path in Path(workdir).iterdir()
            if path.is_file()
        ]

        if not files:
            raise RuntimeError(
                "download failed",
            )

        return max(
            files,
            key=lambda path: path.stat().st_mtime,
        ), info


async def convert_to_ogg_opus(
    source: Path,
    target: Path,
):
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-c:a",
        "libopus",
        "-f",
        "ogg",
        str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    code = await process.wait()

    if code != 0 or not target.exists():
        raise RuntimeError(
            "opus conversion failed",
        )