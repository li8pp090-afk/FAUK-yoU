import asyncio
import hashlib
import shutil
import subprocess
from pathlib import Path

import yt_dlp
from aiogram.types import FSInputFile


DOWNLOAD_DIR = Path("downloads")

MAX_CONCURRENT_PER_USER = 3
WORKER_IDLE_TIMEOUT = 5

workers = {}


def make_job_id(user_id, message_id):
    raw = (
        f"{user_id}:"
        f"{message_id}:"
        f"{asyncio.get_running_loop().time()}"
    )

    return hashlib.sha256(
        raw.encode()
    ).hexdigest()[:32]


def find_file(directory, prefix):
    files = [
        p
        for p in directory.glob(f"{prefix}.*")
        if p.suffix not in (".part", ".ytdl", ".temp")
    ]

    if not files:
        raise FileNotFoundError("Downloaded file not found")

    return max(files, key=lambda p: p.stat().st_mtime)


def remove_path(path):
    if not path:
        return

    try:
        path = Path(path)

        if path.is_file():
            path.unlink()

        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

    except Exception:
        pass


def cleanup_job_files(job_id):
    if not job_id or not DOWNLOAD_DIR.exists():
        return

    for path in DOWNLOAD_DIR.rglob(f"{job_id}.*"):
        remove_path(path)


def download_normal(url, job_id):
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with yt_dlp.YoutubeDL({
            "format": "bestvideo*+bestaudio/best",
            "outtmpl": str(DOWNLOAD_DIR / f"{job_id}.%(ext)s"),
            "noplaylist": True,
        }) as ydl:
            ydl.extract_info(url, download=True)

        return find_file(DOWNLOAD_DIR, job_id)

    except Exception:
        cleanup_job_files(job_id)
        raise


def download_voice(url, job_id):
    source_dir = DOWNLOAD_DIR / "voice_source"
    source_dir.mkdir(parents=True, exist_ok=True)

    source = None
    output = None

    try:
        with yt_dlp.YoutubeDL({
            "format": "bestaudio/best",
            "outtmpl": str(source_dir / f"{job_id}.%(ext)s"),
            "noplaylist": True,
        }) as ydl:
            ydl.extract_info(url, download=True)

        source = find_file(source_dir, job_id)
        output = DOWNLOAD_DIR / f"{job_id}.ogg"

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-c:a",
                "libopus",
                str(output),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=120,
        )

        return output

    except Exception:
        remove_path(output)
        cleanup_job_files(job_id)
        raise

    finally:
        remove_path(source)
        cleanup_job_files(job_id)


async def send_file(bot, chat_id, mode, file_path):
    if mode == "voice":
        sent = await bot.send_voice(
            chat_id=chat_id, voice=FSInputFile(file_path)
        )

        return sent.voice.file_id

    sent = await bot.send_document(
        chat_id=chat_id, document=FSInputFile(file_path)
    )

    return sent.document.file_id


async def send_cached_file(bot, chat_id, mode, file_id):
    try:
        if mode == "voice":
            await bot.send_voice(chat_id=chat_id, voice=file_id)
        else:
            await bot.send_document(chat_id=chat_id, document=file_id)

        return True

    except Exception:
        return False


async def process_job(
    bot,
    job,
    get_cached_file,
    set_cached_file,
    delete_cached_file,
    send_failed,
):
    file_path = None

    try:
        chat_id = job["chat_id"]
        url = job["url"]
        mode = job["mode"]
        job_id = job["job_id"]

        cached = await get_cached_file(mode, url)

        if cached:
            if await send_cached_file(bot, chat_id, mode, cached):
                return

            await delete_cached_file(mode, url)

        downloader = download_voice if mode == "voice" else download_normal

        file_path = await asyncio.to_thread(downloader, url, job_id)

        file_id = await send_file(bot, chat_id, mode, file_path)

        await set_cached_file(mode, url, file_id)

    except asyncio.CancelledError:
        raise

    except Exception:
        try:
            await send_failed(job["chat_id"])
        except Exception:
            pass

    finally:
        if job:
            cleanup_job_files(job.get("job_id"))

        remove_path(file_path)

        file_path = None

        if job:
            job.clear()

        job = None


async def worker(
    bot,
    user_id,
    pop_job,
    get_cached_file,
    set_cached_file,
    delete_cached_file,
    send_failed,
):
    current_task = asyncio.current_task()

    try:
        while True:
            try:
                job = await asyncio.wait_for(
                    pop_job(user_id), timeout=WORKER_IDLE_TIMEOUT
                )
            except asyncio.TimeoutError:
                return

            if not job:
                return

            try:
                await process_job(
                    bot,
                    job,
                    get_cached_file,
                    set_cached_file,
                    delete_cached_file,
                    send_failed,
                )
            finally:
                job = None

    except asyncio.CancelledError:
        raise

    finally:
        tasks = workers.get(user_id)

        if tasks and current_task in tasks:
            tasks.discard(current_task)

            if not tasks:
                workers.pop(user_id, None)


def ensure_workers(
    bot,
    user_id,
    pop_job,
    get_cached_file,
    set_cached_file,
    delete_cached_file,
    send_failed,
):
    tasks = workers.get(user_id)

    if tasks:
        return

    tasks = set()

    workers[user_id] = tasks

    for _ in range(MAX_CONCURRENT_PER_USER):
        task = asyncio.create_task(
            worker(
                bot,
                user_id,
                pop_job,
                get_cached_file,
                set_cached_file,
                delete_cached_file,
                send_failed,
            )
        )

        tasks.add(task)


async def cleanup_old_files():
    if not DOWNLOAD_DIR.exists():
        return

    for path in list(DOWNLOAD_DIR.iterdir()):
        remove_path(path)
