from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from bUTToN import get_notice_state, scope_for_message


ALLOWED_CHAT_TYPES = {
    ChatType.PRIVATE,
    ChatType.GROUP,
    ChatType.SUPERGROUP,
    ChatType.CHANNEL,
}


SERVICE_FIELDS = (
    "new_chat_members",
    "left_chat_member",
    "chat_owner_left",
    "chat_owner_changed",
    "new_chat_title",
    "new_chat_photo",
    "delete_chat_photo",
    "group_chat_created",
    "message_auto_delete_timer_changed",
    "migrate_to_chat_id",
    "migrate_from_chat_id",
    "pinned_message",
    "invoice",
    "successful_payment",
    "refunded_payment",
    "users_shared",
    "chat_shared",
    "gift",
    "unique_gift",
    "gift_upgrade_sent",
    "connected_website",
    "write_access_allowed",
    "passport_data",
    "proximity_alert_triggered",
    "boost_added",
    "chat_background_set",
    "checklist_tasks_done",
    "checklist_tasks_added",
    "direct_message_price_changed",
    "forum_topic_edited",
    "forum_topic_closed",
    "forum_topic_reopened",
    "general_forum_topic_hidden",
    "general_forum_topic_unhidden",
    "giveaway_created",
    "giveaway_winners",
    "giveaway_completed",
    "managed_bot_created",
    "paid_message_price_changed",
    "suggested_post_approved",
    "suggested_post_approval_failed",
    "suggested_post_declined",
    "suggested_post_paid",
    "suggested_post_refunded",
    "video_chat_scheduled",
    "video_chat_started",
    "video_chat_ended",
    "video_chat_participants_invited",
)


def is_service_message(message: Message) -> bool:
    return any(
        getattr(message, field, None) is not None
        for field in SERVICE_FIELDS
    )


def setup_notice_handlers(db_path: str):
    router = Router(name="notice_router")

    @router.message(
        F.chat.type.in_(ALLOWED_CHAT_TYPES),
        is_service_message,
    )
    @router.channel_post(
        F.chat.type.in_(ALLOWED_CHAT_TYPES),
        is_service_message,
    )
    async def delete_service_message(message: Message):
        scope = scope_for_message(message)

        if await get_notice_state(db_path, scope) != "enabled":
            return

        try:
            await message.delete()
        except Exception:
            pass

    return router
