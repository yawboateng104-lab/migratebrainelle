import json
from datetime import UTC, datetime

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.pg_tables import AppEvent
from app.services.pipeline_execution_service import run_creative_request_through_existing_pipeline
from app.services.review_service import (
    approve_and_publish_generated_asset,
    reject_generated_asset,
)
from app.services.video_edit_service import create_edit_revision_from_creative_request


class TelegramReviewError(Exception):
    pass


def _telegram_api_url(method: str) -> str:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise TelegramReviewError("TELEGRAM_BOT_TOKEN is not configured")
    return f"{settings.TELEGRAM_BOT_BASE_URL}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def _post_telegram(method: str, payload: dict) -> dict:
    response = requests.post(_telegram_api_url(method), json=payload, timeout=30)
    response.raise_for_status()

    data = response.json()
    if not data.get("ok"):
        raise TelegramReviewError(f"Telegram API error for {method}: {data}")

    return data


def answer_callback_query(callback_query_id: str, text: str | None = None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return _post_telegram("answerCallbackQuery", payload)


def send_message(chat_id: str | int, text: str, reply_markup: dict | None = None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _post_telegram("sendMessage", payload)


def send_video(
    chat_id: str | int,
    video_url: str,
    caption: str | None = None,
    reply_markup: dict | None = None,
):
    payload = {
        "chat_id": chat_id,
        "video": video_url,
        "supports_streaming": True,
    }
    if caption:
        payload["caption"] = caption[:1024]
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _post_telegram("sendVideo", payload)


def build_review_keyboard(creative_request_id: int, generated_asset_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approve & Publish",
                    "callback_data": f"review:approve:{generated_asset_id}",
                }
            ],
            [
                {
                    "text": "✏️ Request Edit",
                    "callback_data": f"review:edit:{creative_request_id}",
                },
                {
                    "text": "🎵 Add Music Manually",
                    "callback_data": f"review:music_manual:{creative_request_id}",
                },
            ],
            [
                {
                    "text": "❌ Reject",
                    "callback_data": f"review:reject:{generated_asset_id}",
                }
            ],
        ]
    }


def send_generated_asset_for_review(
    db: Session,
    chat_id: str | int,
    creative_request_id: int,
    generated_asset_id: int,
    asset_url: str,
    caption_text: str | None = None,
):
    """
    Legacy helper kept for compatibility.
    Current preferred path is to return a unified result payload to the webhook
    and let telegram.py decide whether to send photo/video/message.
    """
    keyboard = build_review_keyboard(
        creative_request_id=creative_request_id,
        generated_asset_id=generated_asset_id,
    )

    review_text = (
        f"<b>Draft Ready for Review</b>\n\n"
        f"Creative Request ID: {creative_request_id}\n"
        f"Generated Asset ID: {generated_asset_id}\n\n"
        f"<b>Caption Preview:</b>\n{(caption_text or '').strip()}"
    )

    send_video(
        chat_id=chat_id,
        video_url=asset_url,
        caption=(caption_text or "Draft ready for review.")[:1024],
        reply_markup=keyboard,
    )

    send_message(
        chat_id=chat_id,
        text=review_text,
        reply_markup=keyboard,
    )


def _set_pending_edit_session(
    db: Session,
    chat_id: str | int,
    creative_request_id: int,
    music_mode: str | None = None,
):
    event = AppEvent(
        user_id=str(chat_id),
        event_name="telegram_pending_edit",
        feature_name="creative_request_edit",
        event_value=json.dumps(
            {
                "creative_request_id": creative_request_id,
                "music_mode": music_mode,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _get_latest_pending_edit_session(db: Session, chat_id: str | int):
    return (
        db.query(AppEvent)
        .filter(
            AppEvent.user_id == str(chat_id),
            AppEvent.event_name == "telegram_pending_edit",
            AppEvent.feature_name == "creative_request_edit",
        )
        .order_by(AppEvent.id.desc())
        .first()
    )


def _close_pending_edit_session(db: Session, event: AppEvent):
    event.event_name = "telegram_pending_edit_completed"
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _mark_manual_music_preference(db: Session, chat_id: str | int, creative_request_id: int):
    event = AppEvent(
        user_id=str(chat_id),
        event_name="telegram_manual_music_preference",
        feature_name=str(creative_request_id),
        event_value=json.dumps(
            {
                "creative_request_id": creative_request_id,
                "music_mode": "manual_instagram",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_latest_manual_music_preference(db: Session, chat_id: str | int, creative_request_id: int):
    return (
        db.query(AppEvent)
        .filter(
            AppEvent.user_id == str(chat_id),
            AppEvent.event_name == "telegram_manual_music_preference",
            AppEvent.feature_name == str(creative_request_id),
        )
        .order_by(AppEvent.id.desc())
        .first()
    )


def handle_review_callback(db: Session, callback_query: dict):
    callback_query_id = callback_query["id"]
    callback_data = callback_query["data"]
    chat_id = callback_query["message"]["chat"]["id"]

    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "review":
        answer_callback_query(callback_query_id, "Unknown action.")
        return {"handled": False, "reason": "unknown_callback"}

    action = parts[1]
    target_id = int(parts[2])

    if action == "approve":
        answer_callback_query(callback_query_id, "Approving and publishing...")
        result = approve_and_publish_generated_asset(
            generated_asset_id=target_id,
            db=db,
        )
        send_message(
            chat_id=chat_id,
            text=(
                f"<b>Published</b>\n\n"
                f"Generated Asset ID: {target_id}\n"
                f"Status: {result.get('publish_status')}"
            ),
        )
        return {"handled": True, "action": "approve", "result": result}

    if action == "reject":
        answer_callback_query(callback_query_id, "Rejecting draft...")
        result = reject_generated_asset(
            generated_asset_id=target_id,
            db=db,
        )
        send_message(
            chat_id=chat_id,
            text=(
                f"<b>Draft Rejected</b>\n\n"
                f"Generated Asset ID: {target_id}\n"
                f"You can direct a new version whenever you're ready."
            ),
        )
        return {"handled": True, "action": "reject", "result": result}

    if action == "edit":
        answer_callback_query(callback_query_id, "Edit mode enabled.")
        _set_pending_edit_session(
            db=db,
            chat_id=chat_id,
            creative_request_id=target_id,
            music_mode=None,
        )
        send_message(
            chat_id=chat_id,
            text=(
                f"<b>Edit Requested</b>\n\n"
                f"Creative Request ID: {target_id}\n"
                f"Reply with what you want changed.\n\n"
                f"Examples:\n"
                f"- Make it more premium and less busy\n"
                f"- Stronger hook in the first 2 seconds\n"
                f"- Cleaner overlays and calmer movement"
            ),
        )
        return {"handled": True, "action": "edit"}

    if action == "music_manual":
        answer_callback_query(callback_query_id, "Music preference saved.")
        _mark_manual_music_preference(
            db=db,
            chat_id=chat_id,
            creative_request_id=target_id,
        )
        _set_pending_edit_session(
            db=db,
            chat_id=chat_id,
            creative_request_id=target_id,
            music_mode="manual_instagram",
        )
        send_message(
            chat_id=chat_id,
            text=(
                f"<b>Music Preference Saved</b>\n\n"
                f"For Creative Request ID {target_id}, you can add music manually in Instagram "
                f"after the final version is approved.\n\n"
                f"If you also want changes to the video, reply now with your edit notes."
            ),
        )
        return {"handled": True, "action": "music_manual"}

    answer_callback_query(callback_query_id, "Unhandled action.")
    return {"handled": False, "reason": "unhandled_action"}


def handle_pending_edit_reply(db: Session, message: dict):
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if not text:
        return {"handled": False, "reason": "no_text"}

    pending_event = _get_latest_pending_edit_session(db, chat_id)
    if not pending_event:
        return {"handled": False, "reason": "no_pending_edit_session"}

    try:
        event_payload = json.loads(pending_event.event_value or "{}")
    except json.JSONDecodeError:
        event_payload = {}

    creative_request_id = event_payload.get("creative_request_id")
    music_mode = event_payload.get("music_mode")

    if not creative_request_id:
        return {"handled": False, "reason": "missing_creative_request_id"}

    from app.schemas import VideoEditRequestCreate

    edit_payload = VideoEditRequestCreate(
        creative_request_id=creative_request_id,
        edit_goal="revise_video",
        edit_notes=text,
        add_music=(music_mode == "manual_instagram"),
        music_mode=music_mode,
    )

    result = create_edit_revision_from_creative_request(
        db=db,
        payload=edit_payload,
    )

    new_creative_request_id = result["creative_request"].id

    run_result = run_creative_request_through_existing_pipeline(
        db=db,
        creative_request_id=new_creative_request_id,
    )

    pipeline_result = run_result["pipeline_result"]
    generated_asset_id = pipeline_result["generated_asset_id"]
    asset_url = pipeline_result["asset_url"]
    caption_used = pipeline_result.get("caption_used")
    asset_type = pipeline_result.get("asset_type", "video")

    _close_pending_edit_session(db, pending_event)

    keyboard = build_review_keyboard(
        creative_request_id=new_creative_request_id,
        generated_asset_id=generated_asset_id,
    )

    result_payload = {
        "mode": "edited_draft_ready",
        "message": (
            f"🎬 <b>Revision Generated</b>\n\n"
            f"Creative Request ID: {new_creative_request_id}\n"
            f"Generated Asset ID: {generated_asset_id}\n\n"
            f"<b>Caption Preview:</b>\n{(caption_used or '').strip()}"
        ),
        "reply_markup": keyboard,
        "asset_type": asset_type,
    }

    if asset_type == "image":
        result_payload["image_url"] = asset_url
    else:
        result_payload["video_url"] = asset_url

    return {
        "handled": True,
        "action": "edit_reply_processed",
        "new_creative_request_id": new_creative_request_id,
        "generated_asset_id": generated_asset_id,
        "result": result_payload,
    }
