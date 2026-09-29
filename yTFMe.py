async def get_file_extension(os, file_path: str) -> str:
    filename = os.path.basename(file_path)
    parts = filename.rsplit('.', 1)
    if len(parts) > 1:
        return parts[1].lower()
    return ""


async def process_entry(
    os, json, datetime, subprocess, asyncio, sqlite3,
    fs_input_file, mode, entry, idx, user_dir,
    get_cached_file, save_cached_file, generate_file_name,
    txt_download_failed, msg_obj, url, re, dev_rotator,
    inline_keyboard_markup, inline_keyboard_button, btn_style,
    takeoff_env
):
    entry_url = entry.get("webpage_url") or entry.get("url") or url
    cached_id = get_cached_file(sqlite3, entry_url, mode)
    if cached_id:
        return {"type": "cached", "file_id": cached_id, "url": entry_url}

    uploader = entry.get("uploader") or entry.get("channel") or ""
    title = entry.get("title") or ""
    upload_date_str = entry.get("upload_date")
    actual_date = None
    if upload_date_str and len(upload_date_str) == 8:
        try:
            actual_date = datetime.datetime.strptime(upload_date_str, "%Y%m%d").date()
        except Exception:
            pass

    base_name = generate_file_name(re, datetime, uploader, title, actual_date)

    if mode == "voice":
        download_template = os.path.join(user_dir, f"audio_{idx}.%(ext)s")
        dl_cmd = ["yt-dlp", "-f", "ba/b", "-o", download_template, entry_url]
        proc = await asyncio.create_subprocess_exec(*dl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await proc.communicate()

        downloaded_files = [f for f in os.listdir(user_dir) if f.startswith(f"audio_{idx}.")]
        if not downloaded_files:
            return None

        input_audio = os.path.join(user_dir, downloaded_files[0])
        output_ogg = os.path.join(user_dir, f"{base_name}_{idx}.ogg")

        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_audio, "-c:a", "libopus", output_ogg]
        proc_ff = await asyncio.create_subprocess_exec(*ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await proc_ff.communicate()

        if os.path.exists(output_ogg):
            try:
                sent_msg = await msg_obj.reply_voice(voice=fs_input_file(output_ogg))
                if sent_msg and sent_msg.voice:
                    save_cached_file(sqlite3, entry_url, sent_msg.voice.file_id, "voice")
            except Exception:
                reply_markup = dev_rotator.build_dev_keyboard(
                    inline_keyboard_markup, inline_keyboard_button, btn_style, takeoff_env
                )
                await msg_obj.reply(txt_download_failed, reply_markup=reply_markup)
        else:
            reply_markup = dev_rotator.build_dev_keyboard(
                inline_keyboard_markup, inline_keyboard_button, btn_style, takeoff_env
            )
            await msg_obj.reply(txt_download_failed, reply_markup=reply_markup)

        return "processed"

    else:
        video_template = os.path.join(user_dir, f"raw_v_{idx}.%(ext)s")
        audio_template = os.path.join(user_dir, f"raw_a_{idx}.%(ext)s")

        dl_cmd = [
            "yt-dlp",
            "-f", "bv", "-o", video_template,
            "-f", "ba", "-o", audio_template,
            entry_url
        ]
        proc = await asyncio.create_subprocess_exec(*dl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await proc.communicate()

        v_files = [f for f in os.listdir(user_dir) if f.startswith(f"raw_v_{idx}.")]
        a_files = [f for f in os.listdir(user_dir) if f.startswith(f"raw_a_{idx}.")]

        if v_files and a_files:
            v_path = os.path.join(user_dir, v_files[0])
            a_path = os.path.join(user_dir, a_files[0])

            ext = await get_file_extension(os, v_path)
            final_name = f"{base_name}_{idx}.{ext}" if ext else f"{base_name}_{idx}"
            final_path = os.path.join(user_dir, final_name)

            ffmpeg_cmd = ["ffmpeg", "-y", "-i", v_path, "-i", a_path, "-c", "copy", final_path]
            proc_ff = await asyncio.create_subprocess_exec(*ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            await proc_ff.communicate()

            if os.path.exists(final_path):
                return {"type": "file", "path": final_path, "url": entry_url}

        single_template = os.path.join(user_dir, f"raw_s_{idx}.%(ext)s")
        dl_single_cmd = ["yt-dlp", "-f", "b", "-o", single_template, entry_url]
        proc_s = await asyncio.create_subprocess_exec(*dl_single_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await proc_s.communicate()

        s_files = [f for f in os.listdir(user_dir) if f.startswith(f"raw_s_{idx}.")]
        if not s_files:
            return None

        s_path = os.path.join(user_dir, s_files[0])
        ext = await get_file_extension(os, s_path)
        final_name = f"{base_name}_{idx}.{ext}" if ext else f"{base_name}_{idx}"
        final_path = os.path.join(user_dir, final_name)

        os.rename(s_path, final_path)
        return {"type": "file", "path": final_path, "url": entry_url}


async def execute_media_download(
    os, json, shutil, datetime, subprocess, asyncio, sqlite3,
    fs_input_file, input_media_document, message,
    get_mode, get_cached_file, save_cached_file, generate_file_name,
    txt_start_download, txt_download_failed, msg_obj, url: str, key: str, re,
    dev_rotator, inline_keyboard_markup, inline_keyboard_button, btn_style,
    takeoff_env
):
    mode = get_mode(sqlite3, key)

    cached_id = get_cached_file(sqlite3, url, mode)
    if cached_id:
        try:
            if mode == "voice":
                await msg_obj.reply_voice(voice=cached_id)
            else:
                await msg_obj.reply_document(document=cached_id)
            return
        except Exception:
            pass

    try:
        reply_markup = dev_rotator.build_dev_keyboard(
            inline_keyboard_markup, inline_keyboard_button, btn_style, takeoff_env
        )
        await msg_obj.reply(txt_start_download, reply_markup=reply_markup)
    except Exception:
        pass

    base_dir = os.path.join(os.getcwd(), "downloads")
    user_dir = os.path.join(base_dir, str(msg_obj.from_user.id))
    os.makedirs(user_dir, exist_ok=True)

    try:
        info_cmd = ["yt-dlp", "--dump-json", "--flat-playlist", url]
        proc = await asyncio.create_subprocess_exec(*info_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            reply_markup = dev_rotator.build_dev_keyboard(
                inline_keyboard_markup, inline_keyboard_button, btn_style, takeoff_env
            )
            await msg_obj.reply(txt_download_failed, reply_markup=reply_markup)
            return

        lines = [line for line in stdout.decode('utf-8', errors='ignore').strip().split('\n') if line.strip()]

        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass

        if not entries:
            reply_markup = dev_rotator.build_dev_keyboard(
                inline_keyboard_markup, inline_keyboard_button, btn_style, takeoff_env
            )
            await msg_obj.reply(txt_download_failed, reply_markup=reply_markup)
            return

        downloaded_documents = []
        for idx, entry in enumerate(entries):
            res = await process_entry(
                os, json, datetime, subprocess, asyncio, sqlite3,
                fs_input_file, mode, entry, idx, user_dir,
                get_cached_file, save_cached_file, generate_file_name,
                txt_download_failed, msg_obj, url, re, dev_rotator,
                inline_keyboard_markup, inline_keyboard_button, btn_style,
                takeoff_env
            )
            if res and mode != "voice":
                downloaded_documents.append(res)

        if mode == "normal" and downloaded_documents:
            chunk_size = 8
            for i in range(0, len(downloaded_documents), chunk_size):
                chunk = downloaded_documents[i:i + chunk_size]

                if len(chunk) == 1:
                    item = chunk[0]
                    if item["type"] == "cached":
                        await msg_obj.reply_document(document=item["file_id"])
                    else:
                        sent_msg = await msg_obj.reply_document(document=fs_input_file(item["path"]))
                        if sent_msg and sent_msg.document:
                            save_cached_file(sqlite3, item["url"], sent_msg.document.file_id, "normal")
                else:
                    media_group = [
                        input_media_document(
                            media=item["file_id"] if item["type"] == "cached" else fs_input_file(item["path"])
                        )
                        for item in chunk
                    ]
                    sent_msgs = await msg_obj.reply_media_group(media=media_group)
                    if sent_msgs:
                        for idx_msg, sent_msg in enumerate(sent_msgs):
                            if sent_msg.document and idx_msg < len(chunk):
                                item = chunk[idx_msg]
                                if item["type"] == "file":
                                    save_cached_file(sqlite3, item["url"], sent_msg.document.file_id, "normal")

    except Exception:
        try:
            reply_markup = dev_rotator.build_dev_keyboard(
                inline_keyboard_markup, inline_keyboard_button, btn_style, takeoff_env
            )
            await msg_obj.reply(txt_download_failed, reply_markup=reply_markup)
        except Exception:
            pass
    finally:
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir, ignore_errors=True)
