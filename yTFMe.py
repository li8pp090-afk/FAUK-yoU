import asyncio
import shutil
import subprocess
from pathlib import Path

import yt_dlp


def _get_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        raise RuntimeError

    return ffmpeg


def extract_info(url):
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(options) as downloader:
        return downloader.extract_info(
            url,
            download=False,
        )


def _download(
    url,
    output_template,
    selector,
):
    options = {
        "format": selector,
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": False,
    }

    with yt_dlp.YoutubeDL(options) as downloader:
        return downloader.extract_info(
            url,
            download=True,
        )


def run_normal_download(
    url,
    output_template,
):
    return asyncio.to_thread(
        _download,
        url,
        output_template,
        "bestvideo,bestaudio/best",
    )


def run_voice_download(
    url,
    output_template,
):
    return asyncio.to_thread(
        _download,
        url,
        output_template,
        "bestaudio",
    )


def get_requested_downloads(result):
    requested = result.get(
        "requested_downloads"
    )

    if requested:
        return [
            item
            for item in requested
            if item
        ]

    return [result]


def get_video_download(result):
    for item in get_requested_downloads(result):
        if item.get("vcodec") not in (
            None,
            "none",
        ):
            return item

    return None


def get_audio_download(result):
    for item in get_requested_downloads(result):
        if item.get("acodec") not in (
            None,
            "none",
        ):
            return item

    return None


def get_download_path(download):
    filepath = download.get("filepath")

    if filepath:
        return Path(filepath)

    filename = download.get("_filename")

    if filename:
        return Path(filename)

    return None


def get_video_container(video):
    container = video.get("container")

    if container:
        return container

    return video.get("ext")


def _merge_video_audio(
    video_path,
    audio_path,
    output_path,
    video_info,
):
    ffmpeg = _get_ffmpeg()
    container = get_video_container(
        video_info
    )

    if not container:
        raise RuntimeError

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        "-f",
        container,
        str(output_path),
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return output_path


def run_merge(
    video_path,
    audio_path,
    output_path,
    video_info,
):
    return asyncio.to_thread(
        _merge_video_audio,
        video_path,
        audio_path,
        output_path,
        video_info,
    )


def _voice_conversion(
    audio_path,
    output_path,
):
    ffmpeg = _get_ffmpeg()

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(audio_path),
        "-c:a",
        "libopus",
        "-f",
        "ogg",
        str(output_path),
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return output_path


def run_voice_conversion(
    audio_path,
    output_path,
):
    return asyncio.to_thread(
        _voice_conversion,
        audio_path,
        output_path,
    )