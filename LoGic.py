import asyncio
import uuid
from collections import deque

import CAsh
import NAMe
import Reply


MAX_ACTIVE = 3
MAX_QUEUE = 3

USER_STATES = {}
USER_LOCKS = {}


def get_user_state(user_id):
    if user_id not in USER_STATES:
        USER_STATES[user_id] = {
            "active": 0,
            "queue": deque()
        }

    return USER_STATES[user_id]


def get_user_lock(user_id):
    if user_id not in USER_LOCKS:
        USER_LOCKS[user_id] = asyncio.Lock()

    return USER_LOCKS[user_id]


async def run_job(
    bot,
    user_id,
    message,
    url,
    task_id
):
    try:
        await NAMe.process_job(
            bot,
            message,
            url,
            task_id
        )

    finally:
        state = get_user_state(user_id)
        state["active"] -= 1

        while (
            state["queue"]
            and state["active"] < MAX_ACTIVE
        ):
            next_message, next_url, next_task_id = (
                state["queue"].popleft()
            )

            state["active"] += 1

            await CAsh.update_task(
                next_task_id,
                "active"
            )

            asyncio.create_task(
                run_job(
                    bot,
                    user_id,
                    next_message,
                    next_url,
                    next_task_id
                )
            )


async def message_handler(
    bot,
    message
):
    if not message.text:
        return

    url = message.text.strip()

    if not NAMe.is_url(url):
        return

    if NAMe.is_blocked_url(url):
        return

    user_id = message.from_user.id
    state = get_user_state(user_id)
    lock = get_user_lock(user_id)

    async with lock:
        if (
            state["active"] >= MAX_ACTIVE
            and len(state["queue"]) >= MAX_QUEUE
        ):
            return

        await CAsh.add_user(
            user_id
        )

        task_id = str(
            uuid.uuid4()
        )

        if state["active"] < MAX_ACTIVE:
            state["active"] += 1

            await CAsh.add_task(
                task_id,
                user_id,
                "active"
            )

            asyncio.create_task(
                run_job(
                    bot,
                    user_id,
                    message,
                    url,
                    task_id
                )
            )

        else:
            state["queue"].append(
                (
                    message,
                    url,
                    task_id
                )
            )

            await CAsh.add_task(
                task_id,
                user_id,
                "queued"
            )