import subprocess
from pathlib import Path

import yt_dlp


def _run_ffmpeg(args):
    completed = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip()
            or "FFmpeg failed"
        )

    return completed


def _extract_info(url, options):
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(
            url,
            download=False,
        )


def _download_one(
    url,
    format_id,
    output_template,
    options,
):
    ydl_options = dict(options)

    ydl_options.update(
        {
            "format": format_id,
            "outtmpl": output_template,
            "noplaylist": True,
            "postprocessors": [],
        }
    )

    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        info = ydl.extract_info(
            url,
            download=True,
        )

        return ydl.prepare_filename(info)


def _find_downloaded_file(
    path_hint,
    directory,
):
    path_hint = Path(path_hint)

    if (
        path_hint.exists()
        and path_hint.is_file()
    ):
        return path_hint

    candidates = [
        path
        for path in directory.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            not in {".part", ".ytdl"}
        )
    ]

    if not candidates:
        raise FileNotFoundError(
            "Downloaded file was not found"
        )

    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def _base_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "overwrites": False,
        "continuedl": True,
        "retries": 3,
        "fragment_retries": 3,
    }


def _select_normal(url):
    options = _base_options()
    options["format"] = "bv+ba/b"

    return _extract_info(
        url,
        options,
    )


def _select_voice(url):
    options = _base_options()
    options["format"] = "ba/b"

    return _extract_info(
        url,
        options,
    )


def _merge_separate_streams(
    video_path,
    audio_path,
    output_path,
):
    args = [
        "ffmpeg",
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
        str(output_path),
    ]

    _run_ffmpeg(args)

    return output_path


def _convert_voice(
    audio_path,
    output_path,
):
    args = [
        "ffmpeg",
        "-i",
        str(audio_path),
        "-map",
        "0:a:0",
        "-c:a",
        "libopus",
        "-f",
        "ogg",
        str(output_path),
    ]

    _run_ffmpeg(args)

    return output_path


def _download_selected_formats(
    url,
    info,
    work_dir,
):
    requested = info.get(
        "requested_formats"
    )

    if requested and len(requested) >= 2:
        video_format = next(
            item
            for item in requested
            if (
                item.get("vcodec")
                not in (None, "none")
                and item.get("acodec")
                in (None, "none")
            )
        )

        audio_format = next(
            item
            for item in requested
            if (
                item.get("acodec")
                not in (None, "none")
                and item.get("vcodec")
                in (None, "none")
            )
        )

        video_template = str(
            work_dir
            / "video_%(id)s.%(ext)s"
        )

        audio_template = str(
            work_dir
            / "audio_%(id)s.%(ext)s"
        )

        video_hint = _download_one(
            url,
            video_format["format_id"],
            video_template,
            _base_options(),
        )

        video_path = _find_downloaded_file(
            video_hint,
            work_dir,
        )

        audio_hint = _download_one(
            url,
            audio_format["format_id"],
            audio_template,
            _base_options(),
        )

        audio_path = _find_downloaded_file(
            audio_hint,
            work_dir,
        )

        output_path = (
            work_dir
            / f"merged{video_path.suffix}"
        )

        _merge_separate_streams(
            video_path,
            audio_path,
            output_path,
        )

        return output_path

    format_id = info.get("format_id")

    if not format_id:
        raise RuntimeError(
            "No downloadable format selected"
        )

    template = str(
        work_dir
        / "single_%(id)s.%(ext)s"
    )

    hint = _download_one(
        url,
        format_id,
        template,
        _base_options(),
    )

    return _find_downloaded_file(
        hint,
        work_dir,
    )


def _download_voice_selected(
    url,
    info,
    work_dir,
):
    requested = (
        info.get("requested_formats")
        or []
    )

    if requested:
        audio_format = next(
            (
                item
                for item in requested
                if item.get("acodec")
                not in (None, "none")
            ),
            None,
        )
    else:
        audio_format = None

    format_id = (
        audio_format["format_id"]
        if audio_format
        else info.get("format_id")
    )

    if not format_id:
        raise RuntimeError(
            "No audio format selected"
        )

    template = str(
        work_dir
        / "audio_%(id)s.%(ext)s"
    )

    hint = _download_one(
        url,
        format_id,
        template,
        _base_options(),
    )

    audio_path = _find_downloaded_file(
        hint,
        work_dir,
    )

    output_path = (
        work_dir / "voice.ogg"
    )

    _convert_voice(
        audio_path,
        output_path,
    )

    return output_path


def download_normal(
    url,
    work_dir,
):
    info = _select_normal(url)

    return (
        _download_selected_formats(
            url,
            info,
            work_dir,
        ),
        info,
    )


def download_voice(
    url,
    work_dir,
):
    info = _select_voice(url)

    return (
        _download_voice_selected(
            url,
            info,
            work_dir,
        ),
        info,
    )