import os
import re

UPPER_TARGETS = set("ATFGUJNML")

def custom_case_transform(text: str) -> str:
    result = []
    for char in text:
        upper_char = char.upper()
        if upper_char in UPPER_TARGETS:
            result.append(upper_char)
        else:
            result.append(char.lower())
    return "".join(result)

def clean_filename_part(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r'[^\w\s\u0600-\u06FF_-]', '', text)
    cleaned = cleaned.replace('_', '___TEMP_UNDERSCORE___')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.replace('___TEMP_UNDERSCORE___', '_')
    cleaned = custom_case_transform(cleaned)
    return cleaned.strip()

def process_downloaded_filenames(tmp_dir: str) -> list[str]:
    raw_files = sorted([
        f for f in os.listdir(tmp_dir)
        if not f.endswith(".ogg") and os.path.isfile(os.path.join(tmp_dir, f))
    ])

    if not raw_files:
        return []

    downloaded_files = []
    for file_name in raw_files:
        old_path = os.path.join(tmp_dir, file_name)
        name_without_ext, ext = os.path.splitext(file_name)
        
        cleaned_name = clean_filename_part(name_without_ext)
        if not cleaned_name:
            cleaned_name = custom_case_transform("audio")
        
        ext_transformed = custom_case_transform(ext)
        new_file_name = f"{cleaned_name}{ext_transformed}"
        new_path = os.path.join(tmp_dir, new_file_name)
        
        os.rename(old_path, new_path)
        downloaded_files.append(new_path)

    return downloaded_files
