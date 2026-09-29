def format_text_cases(text: str) -> str:
    if not text:
        return ""
    upper_targets = set("ATFGUJNML")
    result = []
    for char in text:
        if 'a' <= char <= 'z':
            result.append(char.upper() if char.upper() in upper_targets else char)
        elif 'A' <= char <= 'Z':
            result.append(char if char in upper_targets else char.lower())
        else:
            result.append(char)
    return "".join(result)


def clean_filename_part(re, text: str) -> str:
    if not text:
        return ""
    formatted = format_text_cases(text)
    cleaned = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s_\&\-]', '', formatted)
    return re.sub(r'\s+', ' ', cleaned).strip()


def generate_file_name(
    re,
    datetime,
    publisher_or_channel: str,
    title: str,
    actual_date=None
) -> str:
    publisher_clean = clean_filename_part(re, publisher_or_channel)
    title_clean = clean_filename_part(re, title)

    if not title_clean:
        if actual_date:
            title_clean = actual_date.strftime("%Y-%m-%d")
        else:
            title_clean = datetime.date.today().strftime("%Y-%m-%d")

    if publisher_clean and title_clean:
        return f"{publisher_clean} - {title_clean}"
    return publisher_clean or title_clean


def is_telegram_url(re, text: str) -> bool:
    telegram_pattern = r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.dog)/[^\s]+'
    return bool(re.search(telegram_pattern, text, re.IGNORECASE))


def is_url(re, text: str) -> bool:
    if is_telegram_url(re, text):
        return False
    return bool(re.search(r'https?://[^\s]+', text))


class DownloadQueueManager:
    def __init__(self, asyncio, max_concurrent=3, max_waiting=3):
        self.asyncio = asyncio
        self.max_concurrent = max_concurrent
        self.max_waiting = max_waiting
        self.active_tasks = {}
        self.waiting_counts = {}

    def can_enqueue(self, key: str) -> bool:
        active = self.active_tasks.get(key, 0)
        waiting = self.waiting_counts.get(key, 0)
        return active < self.max_concurrent or waiting < self.max_waiting

    async def acquire(self, key: str) -> bool:
        if key not in self.active_tasks:
            self.active_tasks[key] = 0
            self.waiting_counts[key] = 0

        if self.active_tasks[key] < self.max_concurrent:
            self.active_tasks[key] += 1
            return True

        if self.waiting_counts[key] < self.max_waiting:
            self.waiting_counts[key] += 1
            while self.active_tasks[key] >= self.max_concurrent:
                await self.asyncio.sleep(1)
            self.waiting_counts[key] -= 1
            self.active_tasks[key] += 1
            return True

        return False

    def release(self, key: str):
        if key in self.active_tasks and self.active_tasks[key] > 0:
            self.active_tasks[key] -= 1
