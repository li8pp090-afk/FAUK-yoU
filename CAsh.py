import hashlib
import json


MAX_CONCURRENT_PER_USER = 3
QUEUE_SIZE_PER_USER = 3


def mode_key(user_id):
    return f"user:{user_id}:mode"


def queue_key(user_id):
    return f"user:{user_id}:queue"


def reply_key(user_id):
    return f"user:{user_id}:reply"


def file_cache_key(
    mode,
    url
):
    return (
        f"file:{mode}:"
        f"{hashlib.sha256(url.encode()).hexdigest()}"
    )


async def get_mode(
    db,
    user_id
):
    mode = await db.get(
        mode_key(user_id)
    )

    return (
        mode
        if mode in (
            "normal",
            "voice"
        )
        else "normal"
    )


async def set_mode(
    db,
    user_id,
    mode
):
    await db.set(
        mode_key(user_id),
        mode
    )


async def get_reply_index(
    db,
    user_id,
    count
):
    key = reply_key(user_id)

    value = await db.get(key)

    index = int(
        value or 0
    ) % count

    await db.set(
        key,
        (index + 1) % count
    )

    return index


async def get_cached_file(
    db,
    mode,
    url
):
    return await db.get(
        file_cache_key(
            mode,
            url
        )
    )


async def set_cached_file(
    db,
    mode,
    url,
    file_id
):
    await db.set(
        file_cache_key(
            mode,
            url
        ),
        file_id
    )


async def delete_cached_file(
    db,
    mode,
    url
):
    await db.delete(
        file_cache_key(
            mode,
            url
        )
    )


PUSH_JOB_SCRIPT = """
local length = redis.call('LLEN', KEYS[1])

if length >= tonumber(ARGV[1]) then
    return 0
end

redis.call(
    'RPUSH',
    KEYS[1],
    ARGV[2]
)

return 1
"""


async def push_job(
    db,
    user_id,
    job
):
    result = await db.eval(
        PUSH_JOB_SCRIPT,
        1,
        queue_key(user_id),
        QUEUE_SIZE_PER_USER,
        json.dumps(
            job,
            ensure_ascii=False
        )
    )

    return bool(result)


async def pop_job(
    db,
    user_id
):
    result = await db.blpop(
        queue_key(user_id),
        timeout=5
    )

    if not result:
        return None

    return json.loads(
        result[1]
    )


async def clear_all_queues(db):
    keys = []

    async for key in db.scan_iter(
        match="user:*:queue"
    ):
        keys.append(key)

    if keys:
        await db.delete(
            *keys
        )