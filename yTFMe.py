import os
import subprocess

import yt_dlp

from SeTTiNGs import build_filename


def get_entries(info):
    entries = info.get("entries")

    if not entries:
        return [info]

    result = []

    for entry in entries:
        if entry:
            result.append(entry)

    return result


def get_entry_url(entry):
    return (
        entry.get("webpage_url")
        or entry.get("original_url")
        or entry.get("url")
    )


def download_virtual_one(url, output_dir):
    info_options = {
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False
    }

    with yt_dlp.YoutubeDL(info_options) as ydl:
        info = ydl.extract_info(
            url,
            download=False
        )

    formats = info.get("formats") or []

    separate_video = [
        fmt for fmt in formats
        if fmt.get("vcodec") not in (None, "none")
        and fmt.get("acodec") == "none"
    ]

    separate_audio = [
        fmt for fmt in formats
        if fmt.get("acodec") not in (None, "none")
        and fmt.get("vcodec") == "none"
    ]

    if separate_video and separate_audio:
        format_selector = "bestvideo+bestaudio/best"
    else:
        format_selector = "best"

    output_template = os.path.join(
        output_dir,
        "%(uploader)s - %(title)s.%(ext)s"
    )

    options = {
        "format": format_selector,
        "outtmpl": output_template
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        downloaded_info = ydl.extract_info(
            url,
            download=True
        )

        prepared_filename = ydl.prepare_filename(
            downloaded_info
        )

    directory = os.path.dirname(prepared_filename)

    if not os.path.exists(prepared_filename):
        files = [
            os.path.join(directory, filename)
            for filename in os.listdir(directory)
            if os.path.isfile(
                os.path.join(directory, filename)
            )
        ]

        if not files:
            raise FileNotFoundError(
                "Downloaded file was not found"
            )

        prepared_filename = max(
            files,
            key=os.path.getmtime
        )

    extension = os.path.splitext(
        prepared_filename
    )[1].lstrip(".")

    final_path = os.path.join(
        directory,
        build_filename(
            downloaded_info,
            extension
        )
    )

    if prepared_filename != final_path:
        if os.path.exists(final_path):
            os.remove(final_path)

        os.replace(
            prepared_filename,
            final_path
        )

    return final_path


def download_virtual(url, output_dir="downloads"):
    os.makedirs(output_dir, exist_ok=True)

    info_options = {
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False
    }

    with yt_dlp.YoutubeDL(info_options) as ydl:
        info = ydl.extract_info(
            url,
            download=False
        )

    entries = get_entries(info)

    file_paths = []

    for entry in entries:
        entry_url = get_entry_url(entry)

        if not entry_url:
            continue

        file_path = download_virtual_one(
            entry_url,
            output_dir
        )

        file_paths.append(file_path)

    return file_paths


def download_voice_one(url, output_dir):
    output_template = os.path.join(
        output_dir,
        "%(uploader)s - %(title)s.%(ext)s"
    )

    options = {
        "format": "bestaudio",
        "outtmpl": output_template
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=True
        )

        source_file = ydl.prepare_filename(
            info
        )

    if not os.path.exists(source_file):
        files = [
            os.path.join(output_dir, filename)
            for filename in os.listdir(output_dir)
            if os.path.isfile(
                os.path.join(output_dir, filename)
            )
        ]

        if not files:
            raise FileNotFoundError(
                "Audio file was not found"
            )

        source_file = max(
            files,
            key=os.path.getmtime
        )

    final_path = os.path.join(
        output_dir,
        build_filename(info, "ogg")
    )

    subprocess.run(
        [
            "ffmpeg",
            "-i",
            source_file,
            "-c:a",
            "libopus",
            final_path
        ],
        check=True
    )

    if source_file != final_path and os.path.exists(source_file):
        os.remove(source_file)

    return final_path


def download_voice(url, output_dir="downloads"):
    os.makedirs(output_dir, exist_ok=True)

    info_options = {
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False
    }

    with yt_dlp.YoutubeDL(info_options) as ydl:
        info = ydl.extract_info(
            url,
            download=False
        )

    entries = get_entries(info)

    file_paths = []

    for entry in entries:
        entry_url = get_entry_url(entry)

        if not entry_url:
            continue

        file_path = download_voice_one(
            entry_url,
            output_dir
        )

        file_paths.append(file_path)

    return file_paths