import os
import re
import shutil
import subprocess
import tempfile

import yt_dlp

from SeTTiNGs import build_filename


DOWNLOAD_ROOT = "downloads"


def create_job_directory():
    os.makedirs(
        DOWNLOAD_ROOT,
        exist_ok=True
    )

    return tempfile.mkdtemp(
        prefix="job_",
        dir=DOWNLOAD_ROOT
    )


def cleanup_path(path):
    if not path:
        return

    try:
        if os.path.isdir(path):
            shutil.rmtree(
                path,
                ignore_errors=True
            )
        elif os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


def get_entries(info):
    entries = info.get("entries")

    if not entries:
        return [info]

    return [
        entry
        for entry in entries
        if entry
    ]


def get_entry_url(entry):
    return (
        entry.get("webpage_url")
        or entry.get("original_url")
        or entry.get("url")
    )


def get_downloaded_path(
    info,
    job_directory,
    ydl
):
    filepath = info.get("filepath")

    if filepath:
        filepath = os.path.abspath(
            filepath
        )

        if os.path.isfile(filepath):
            return filepath

    prepared_filename = ydl.prepare_filename(
        info
    )

    prepared_filename = os.path.abspath(
        prepared_filename
    )

    if os.path.isfile(
        prepared_filename
    ):
        return prepared_filename

    files = []

    for root, _, filenames in os.walk(
        job_directory
    ):
        for filename in filenames:
            file_path = os.path.join(
                root,
                filename
            )

            if os.path.isfile(
                file_path
            ):
                files.append(
                    file_path
                )

    if not files:
        raise FileNotFoundError(
            "Downloaded file was not found"
        )

    return max(
        files,
        key=os.path.getmtime
    )


def rename_downloaded_file(
    source_file,
    info
):
    extension = os.path.splitext(
        source_file
    )[1].lstrip(".")

    if not extension:
        extension = info.get(
            "ext"
        ) or "bin"

    final_name = build_filename(
        info,
        extension
    )

    final_path = os.path.join(
        os.path.dirname(source_file),
        final_name
    )

    if (
        os.path.abspath(source_file)
        == os.path.abspath(final_path)
    ):
        return final_path

    if os.path.exists(
        final_path
    ):
        base, ext = os.path.splitext(
            final_path
        )

        counter = 2

        while os.path.exists(
            f"{base} ({counter}){ext}"
        ):
            counter += 1

        final_path = (
            f"{base} ({counter}){ext}"
        )

    os.replace(
        source_file,
        final_path
    )

    return final_path


def get_download_options(
    job_directory,
    format_name
):
    return {
        "format": format_name,
        "outtmpl": os.path.join(
            job_directory,
            "%(id)s.%(ext)s"
        )
    }


def get_info_options():
    return {}


def get_media_info(url):
    with yt_dlp.YoutubeDL(
        get_info_options()
    ) as ydl:
        return ydl.extract_info(
            url,
            download=False
        )


def download_file(
    url,
    job_directory,
    format_name
):
    options = get_download_options(
        job_directory,
        format_name
    )

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:
        info = ydl.extract_info(
            url,
            download=True
        )

        downloaded_path = get_downloaded_path(
            info,
            job_directory,
            ydl
        )

    return (
        downloaded_path,
        info
    )


def download_virtual_one(
    url,
    job_directory
):
    source_file, info = download_file(
        url,
        job_directory,
        "bestvideo+bestaudio/best"
    )

    return rename_downloaded_file(
        source_file,
        info
    )


def download_virtual(url):
    job_directory = create_job_directory()

    try:
        info = get_media_info(
            url
        )

        entries = get_entries(
            info
        )

        file_paths = []

        for entry in entries:
            entry_url = get_entry_url(
                entry
            )

            if not entry_url:
                continue

            file_path = download_virtual_one(
                entry_url,
                job_directory
            )

            file_paths.append(
                file_path
            )

        if not file_paths:
            raise FileNotFoundError(
                "No downloadable files were found"
            )

        return (
            job_directory,
            file_paths
        )

    except Exception:
        cleanup_path(
            job_directory
        )
        raise


def download_voice_one(
    url,
    job_directory
):
    source_file, info = download_file(
        url,
        job_directory,
        "bestaudio/best"
    )

    final_path = os.path.join(
        job_directory,
        build_filename(
            info,
            "ogg"
        )
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            source_file,
            "-vn",
            "-c:a",
            "libopus",
            final_path
        ],
        check=True
    )

    if (
        os.path.abspath(source_file)
        != os.path.abspath(final_path)
    ):
        cleanup_path(
            source_file
        )

    return final_path


def download_voice(url):
    job_directory = create_job_directory()

    try:
        info = get_media_info(
            url
        )

        entries = get_entries(
            info
        )

        file_paths = []

        for entry in entries:
            entry_url = get_entry_url(
                entry
            )

            if not entry_url:
                continue

            file_path = download_voice_one(
                entry_url,
                job_directory
            )

            file_paths.append(
                file_path
            )

        if not file_paths:
            raise FileNotFoundError(
                "No downloadable audio files were found"
            )

        return (
            job_directory,
            file_paths
        )

    except Exception:
        cleanup_path(
            job_directory
        )
        raise


def parse_duration_part(value):
    value = value.strip()

    if re.fullmatch(
        r"\d+",
        value
    ):
        return float(value)

    match = re.fullmatch(
        r"(\d+):(\d+)(?:\.(\d+))?",
        value
    )

    if match:
        minutes = int(
            match.group(1)
        )

        seconds = int(
            match.group(2)
        )

        fraction = match.group(3)

        if seconds >= 60:
            raise ValueError

        if fraction:
            fraction_value = int(
                fraction
            ) / (
                10 ** len(fraction)
            )
        else:
            fraction_value = 0

        return (
            minutes * 60
            + seconds
            + fraction_value
        )

    match = re.fullmatch(
        r"(\d+)\.(\d+)",
        value
    )

    if match:
        hours = int(
            match.group(1)
        )

        minutes = int(
            match.group(2)
        )

        if hours > 23:
            raise ValueError

        if minutes >= 60:
            raise ValueError

        return (
            hours * 3600
            + minutes * 60
        )

    match = re.fullmatch(
        r"(\d+)\.(\d+):(\d+)(?:\.(\d+))?",
        value
    )

    if match:
        hours = int(
            match.group(1)
        )

        minutes = int(
            match.group(2)
        )

        seconds = int(
            match.group(3)
        )

        fraction = match.group(4)

        if minutes >= 60:
            raise ValueError

        if seconds >= 60:
            raise ValueError

        if fraction:
            fraction_value = int(
                fraction
            ) / (
                10 ** len(fraction)
            )
        else:
            fraction_value = 0

        return (
            hours * 3600
            + minutes * 60
            + seconds
            + fraction_value
        )

    raise ValueError


def parse_duration_range(value):
    value = value.strip()

    match = re.fullmatch(
        r"(.+?)\s*(?:/|-)\s*(.+)",
        value
    )

    if match:
        start_text = match.group(1).strip()
        end_text = match.group(2).strip()
    else:
        parts = value.split()

        if len(parts) != 2:
            raise ValueError

        start_text = parts[0]
        end_text = parts[1]

    start = parse_duration_part(
        start_text
    )

    end = parse_duration_part(
        end_text
    )

    if start < 0:
        raise ValueError

    if end <= start:
        raise ValueError

    return start, end


def get_media_duration(
    file_path
):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return float(
        result.stdout.strip()
    )


def trim_voice(
    source_file,
    start,
    end,
    output_file
):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            source_file,
            "-ss",
            str(start),
            "-to",
            str(end),
            "-c:a",
            "libopus",
            output_file
        ],
        check=True
    )

    return output_file


def get_virtual(url):
    return download_virtual(
        url
    )


def get_voice(url):
    return download_voice(
        url
    )


def get_voice_edit_range(value):
    return parse_duration_range(
        value
    )


def get_voice_duration(
    file_path
):
    return get_media_duration(
        file_path
    )


def edit_voice(
    source_file,
    start,
    end,
    output_file
):
    return trim_voice(
        source_file,
        start,
        end,
        output_file
    )