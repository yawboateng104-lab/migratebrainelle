import json
import mimetypes
import os
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

import boto3
import requests

from app.config import settings
from app.pg_tables import AppEvent


class TelegramMediaError(Exception):
    pass


def _telegram_api_url(method: str) -> str:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise TelegramMediaError("TELEGRAM_BOT_TOKEN is not configured")
    return f"{settings.TELEGRAM_BOT_BASE_URL}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def _telegram_file_download_url(file_path: str) -> str:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise TelegramMediaError("TELEGRAM_BOT_TOKEN is not configured")
    safe_path = quote(file_path.lstrip("/"), safe="/")
    return f"{settings.TELEGRAM_BOT_BASE_URL}/file/bot{settings.TELEGRAM_BOT_TOKEN}/{safe_path}"


def _post_telegram(method: str, payload: dict) -> dict:
    response = requests.post(_telegram_api_url(method), json=payload, timeout=60)
    response.raise_for_status()

    data = response.json()
    if not data.get("ok"):
        raise TelegramMediaError(f"Telegram API error for {method}: {data}")

    return data


def _select_best_photo_variant(photo_variants: list[dict]) -> dict:
    if not photo_variants:
        raise TelegramMediaError("No Telegram photo variants found in message")

    def score(item: dict) -> tuple[int, int, int]:
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        file_size = int(item.get("file_size") or 0)
        return (width * height, file_size, width)

    return sorted(photo_variants, key=score, reverse=True)[0]


def _get_telegram_file_path(file_id: str) -> str:
    data = _post_telegram("getFile", {"file_id": file_id})
    result = data.get("result") or {}
    file_path = (result.get("file_path") or "").strip()

    if not file_path:
        raise TelegramMediaError(f"Telegram did not return a file_path for file_id={file_id}")

    return file_path


def _download_telegram_file_bytes(file_path: str) -> tuple[bytes, str]:
    url = _telegram_file_download_url(file_path)
    response = requests.get(url, timeout=300)

    if response.status_code >= 400:
        raise TelegramMediaError(
            f"Failed to download Telegram file: {response.status_code} {response.text}"
        )

    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
    return response.content, content_type or "application/octet-stream"


def _guess_extension(file_path: str, content_type: str, default_ext: str = ".jpg") -> str:
    file_ext = os.path.splitext(file_path)[1].strip()
    if file_ext:
        return file_ext

    guessed = mimetypes.guess_extension(content_type) or default_ext
    if not guessed.startswith("."):
        guessed = f".{guessed}"

    return guessed


def _upload_bytes_to_s3(data: bytes, s3_key: str, content_type: str) -> str:
    s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
    s3_client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=data,
        ContentType=content_type,
    )

    return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"


def _record_uploaded_source_image_event(
    db,
    chat_id: int | str,
    s3_key: str,
    asset_url: str,
    telegram_file_id: str,
    telegram_file_unique_id: str | None = None,
):
    event = AppEvent(
        user_id=str(chat_id),
        event_name="telegram_uploaded_source_image",
        feature_name="source_image",
        event_value=json.dumps(
            {
                "s3_key": s3_key,
                "asset_url": asset_url,
                "telegram_file_id": telegram_file_id,
                "telegram_file_unique_id": telegram_file_unique_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def store_telegram_photo_for_chat(db, message: dict) -> dict:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    photo_variants = message.get("photo") or []

    if not chat_id:
        raise TelegramMediaError("Telegram chat id is missing from photo message")

    best_photo = _select_best_photo_variant(photo_variants)
    telegram_file_id = (best_photo.get("file_id") or "").strip()
    telegram_file_unique_id = (best_photo.get("file_unique_id") or "").strip() or None

    if not telegram_file_id:
        raise TelegramMediaError("Telegram photo message is missing file_id")

    file_path = _get_telegram_file_path(telegram_file_id)
    file_bytes, content_type = _download_telegram_file_bytes(file_path)
    file_ext = _guess_extension(file_path=file_path, content_type=content_type, default_ext=".jpg")

    s3_prefix = (settings.S3_IMAGE_PREFIX or "image-folder/").strip()
    if not s3_prefix.endswith("/"):
        s3_prefix = f"{s3_prefix}/"

    s3_key = f"{s3_prefix}telegram-chat-{chat_id}/{uuid.uuid4()}{file_ext}"
    asset_url = _upload_bytes_to_s3(
        data=file_bytes,
        s3_key=s3_key,
        content_type=content_type or "image/jpeg",
    )

    event = _record_uploaded_source_image_event(
        db=db,
        chat_id=chat_id,
        s3_key=s3_key,
        asset_url=asset_url,
        telegram_file_id=telegram_file_id,
        telegram_file_unique_id=telegram_file_unique_id,
    )

    return {
        "chat_id": str(chat_id),
        "s3_key": s3_key,
        "asset_url": asset_url,
        "telegram_file_id": telegram_file_id,
        "telegram_file_unique_id": telegram_file_unique_id,
        "event_id": event.id,
        "status": "stored",
    }


def get_latest_uploaded_source_image_s3_key_for_chat(db, chat_id: int | str) -> str | None:
    event = (
        db.query(AppEvent)
        .filter(
            AppEvent.user_id == str(chat_id),
            AppEvent.event_name == "telegram_uploaded_source_image",
            AppEvent.feature_name == "source_image",
        )
        .order_by(AppEvent.id.desc())
        .first()
    )
    if not event:
        return None

    try:
        payload = json.loads(event.event_value or "{}")
    except json.JSONDecodeError:
        return None

    s3_key = (payload.get("s3_key") or "").strip()
    return s3_key or None
