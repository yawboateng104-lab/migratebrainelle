from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import mimetypes
import os
import shutil
import tempfile
import time
from urllib.parse import urlparse

import boto3
import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, get_db
from app.integrations.telegram import (
    TelegramError,
    answer_callback_query,
    send_telegram_message,
)
from app.services.telegram_media_service import (
    TelegramMediaError,
    store_telegram_photo_for_chat,
)
from app.services.telegram_review_service import (
    handle_pending_edit_reply,
    handle_review_callback,
)
from app.services.telegram_runtime import finish_chat_job, should_process_update
from app.services.telegram_service import (
    TelegramAgentError,
    handle_callback_action,
    handle_telegram_command,
    run_deferred_workflow,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])

executor = ThreadPoolExecutor(max_workers=4)

TELEGRAM_MEDIA_CACHE_DIR = os.path.join(tempfile.gettempdir(), "telegram_media_cache")
IMAGE_CACHE_TTL_SECONDS = 30 * 60
VIDEO_CACHE_TTL_SECONDS = 60 * 60
CACHE_CLEANUP_MAX_AGE_SECONDS = 2 * 60 * 60


def _get_telegram_bot_api_url(method_name: str) -> str:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN is not configured")

    return f"{settings.TELEGRAM_BOT_BASE_URL}/bot{token}/{method_name}"


def _ensure_cache_dir() -> str:
    os.makedirs(TELEGRAM_MEDIA_CACHE_DIR, exist_ok=True)
    return TELEGRAM_MEDIA_CACHE_DIR


def _cleanup_old_cache_files(max_age_seconds: int = CACHE_CLEANUP_MAX_AGE_SECONDS) -> None:
    cache_dir = _ensure_cache_dir()
    now = time.time()

    try:
        for name in os.listdir(cache_dir):
            path = os.path.join(cache_dir, name)
            if not os.path.isfile(path):
                continue

            try:
                age_seconds = now - os.path.getmtime(path)
                if age_seconds > max_age_seconds:
                    os.remove(path)
            except OSError:
                continue
    except OSError:
        pass


def _is_our_s3_asset_url(media_url: str) -> bool:
    if not media_url:
        return False

    parsed = urlparse(media_url)
    host = (parsed.netloc or "").lower()
    expected_bucket = (settings.S3_BUCKET_NAME or "").strip().lower()
    expected_region = (settings.AWS_REGION or "").strip().lower()

    if not expected_bucket or not expected_region:
        return False

    expected_host = f"{expected_bucket}.s3.{expected_region}.amazonaws.com"
    return host == expected_host


def _extract_s3_key_from_asset_url(media_url: str) -> str:
    parsed = urlparse(media_url)
    key = (parsed.path or "").lstrip("/")
    if not key:
        raise TelegramError(f"Could not extract S3 key from asset URL: {media_url}")
    return key


def _build_downloadable_media_url(media_url: str, expires_in: int = 3600) -> str:
    if not _is_our_s3_asset_url(media_url):
        return media_url

    s3_key = _extract_s3_key_from_asset_url(media_url)

    s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": s3_key,
        },
        ExpiresIn=expires_in,
    )
    return presigned_url


def _cache_key_for_url(media_url: str) -> str:
    return hashlib.sha256(media_url.encode("utf-8")).hexdigest()


def _cache_path_for_url(media_url: str, extension: str) -> str:
    cache_dir = _ensure_cache_dir()
    safe_ext = extension if extension.startswith(".") else f".{extension}"
    return os.path.join(cache_dir, f"{_cache_key_for_url(media_url)}{safe_ext}")


def _is_cache_fresh(path: str, ttl_seconds: int) -> bool:
    if not os.path.exists(path):
        return False

    try:
        age_seconds = time.time() - os.path.getmtime(path)
    except OSError:
        return False

    return age_seconds <= ttl_seconds


def _download_remote_file_to_cache(
    media_url: str,
    default_ext: str,
    ttl_seconds: int,
) -> tuple[str, str]:
    downloadable_url = _build_downloadable_media_url(media_url)

    content_type = ""
    try:
        head_response = requests.head(downloadable_url, timeout=60, allow_redirects=True)
        if head_response.ok:
            content_type = (head_response.headers.get("Content-Type") or "").split(";")[0].strip()
    except requests.RequestException:
        content_type = ""

    guessed_ext = mimetypes.guess_extension(content_type) or default_ext
    if not guessed_ext.startswith("."):
        guessed_ext = f".{guessed_ext}"

    cache_path = _cache_path_for_url(media_url, guessed_ext)

    if _is_cache_fresh(cache_path, ttl_seconds):
        return cache_path, content_type or (mimetypes.guess_type(cache_path)[0] or "application/octet-stream")

    response = requests.get(downloadable_url, timeout=300, stream=True)
    if response.status_code >= 400:
        raise TelegramError(
            f"Failed to download remote media: {response.status_code} {response.text}"
        )

    response_content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
    if response_content_type:
        content_type = response_content_type

    if not content_type:
        content_type = mimetypes.guess_type(cache_path)[0] or "application/octet-stream"

    temp_download_path = f"{cache_path}.part"

    try:
        with open(temp_download_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)

        shutil.move(temp_download_path, cache_path)
    finally:
        if os.path.exists(temp_download_path):
            try:
                os.remove(temp_download_path)
            except OSError:
                pass

    _cleanup_old_cache_files()

    return cache_path, content_type


def _send_telegram_photo_preview(
    chat_id: int | str,
    image_url: str,
    caption: str,
    reply_markup: dict | None = None,
):
    url = _get_telegram_bot_api_url("sendPhoto")

    local_path, content_type = _download_remote_file_to_cache(
        media_url=image_url,
        default_ext=".png",
        ttl_seconds=IMAGE_CACHE_TTL_SECONDS,
    )

    with open(local_path, "rb") as image_file:
        data = {
            "chat_id": str(chat_id),
            "caption": caption[:1024] if caption else "",
        }

        if reply_markup:
            data["reply_markup"] = requests.compat.json.dumps(reply_markup)

        files = {
            "photo": (
                Path(local_path).name,
                image_file,
                content_type or mimetypes.guess_type(local_path)[0] or "image/png",
            )
        }

        response = requests.post(url, data=data, files=files, timeout=300)

    if not response.ok:
        raise TelegramError(
            f"Failed to send Telegram photo preview: {response.status_code} {response.text}"
        )

    data = response.json()
    if not data.get("ok"):
        raise TelegramError(f"Telegram photo preview API error: {data}")

    return data


def _send_telegram_video_preview(
    chat_id: int | str,
    video_url: str,
    caption: str,
    reply_markup: dict | None = None,
):
    url = _get_telegram_bot_api_url("sendVideo")

    local_path, content_type = _download_remote_file_to_cache(
        media_url=video_url,
        default_ext=".mp4",
        ttl_seconds=VIDEO_CACHE_TTL_SECONDS,
    )

    with open(local_path, "rb") as video_file:
        data = {
            "chat_id": str(chat_id),
            "caption": caption[:1024] if caption else "",
            "supports_streaming": "true",
        }

        if reply_markup:
            data["reply_markup"] = requests.compat.json.dumps(reply_markup)

        files = {
            "video": (
                Path(local_path).name,
                video_file,
                content_type or mimetypes.guess_type(local_path)[0] or "video/mp4",
            )
        }

        response = requests.post(url, data=data, files=files, timeout=300)

    if not response.ok:
        raise TelegramError(
            f"Failed to send Telegram video preview: {response.status_code} {response.text}"
        )

    data = response.json()
    if not data.get("ok"):
        raise TelegramError(f"Telegram video preview API error: {data}")

    return data


def _send_result_to_telegram(chat_id: int | str, result: dict):
    message = result.get("message", "")
    reply_markup = result.get("reply_markup")
    image_url = result.get("image_url")
    video_url = result.get("video_url")

    if image_url:
        try:
            _send_telegram_photo_preview(
                chat_id=chat_id,
                image_url=image_url,
                caption=message,
                reply_markup=reply_markup,
            )
            return
        except Exception as exc:
            print(f"[TELEGRAM PHOTO PREVIEW ERROR] {exc}")

    if video_url:
        try:
            _send_telegram_video_preview(
                chat_id=chat_id,
                video_url=video_url,
                caption=message,
                reply_markup=reply_markup,
            )
            return
        except Exception as exc:
            print(f"[TELEGRAM VIDEO PREVIEW ERROR] {exc}")

    send_telegram_message(
        chat_id=chat_id,
        text=message,
        reply_markup=reply_markup,
    )


def _process_deferred_workflow(chat_id: int | str, workflow: str):
    db = SessionLocal()
    try:
        result = run_deferred_workflow(workflow, db, chat_id)
        _send_result_to_telegram(chat_id=chat_id, result=result)
    except Exception as exc:
        error_message = f"❌ Failed to generate draft for {workflow}: {exc}"
        print(f"[TELEGRAM DEFERRED ERROR] {exc}")
        try:
            send_telegram_message(chat_id=chat_id, text=error_message)
        except Exception as send_exc:
            print(f"[TELEGRAM DEFERRED SEND ERROR] {send_exc}")
    finally:
        finish_chat_job(chat_id)
        db.close()


def _process_callback_action(chat_id: int | str, action: str, asset_id: int):
    db = SessionLocal()
    try:
        response_text = handle_callback_action(chat_id=chat_id, action=action, asset_id=asset_id, db=db)
        if isinstance(response_text, dict):
            _send_result_to_telegram(chat_id=chat_id, result=response_text)
        else:
            send_telegram_message(chat_id=chat_id, text=str(response_text))
    except Exception as exc:
        error_message = f"❌ Failed to {action} asset {asset_id}: {exc}"
        print(f"[TELEGRAM CALLBACK ERROR] {exc}")
        try:
            send_telegram_message(chat_id=chat_id, text=error_message)
        except Exception as send_exc:
            print(f"[TELEGRAM CALLBACK SEND ERROR] {send_exc}")
    finally:
        db.close()


def _process_review_callback(callback_query: dict):
    db = SessionLocal()
    try:
        handle_review_callback(db=db, callback_query=callback_query)
    except Exception as exc:
        print(f"[TELEGRAM REVIEW CALLBACK ERROR] {exc}")
        try:
            message = callback_query.get("message", {})
            chat = message.get("chat", {})
            chat_id = chat.get("id")
            if chat_id:
                send_telegram_message(
                    chat_id=chat_id,
                    text=f"❌ Review action failed: {exc}",
                )
        except Exception as send_exc:
            print(f"[TELEGRAM REVIEW CALLBACK SEND ERROR] {send_exc}")
    finally:
        db.close()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if settings.TELEGRAM_WEBHOOK_SECRET_TOKEN:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid Telegram secret token")

    try:
        body = await request.json()
    except Exception as exc:
        print(f"[TELEGRAM BODY ERROR] {exc}")
        return {"status": "ignored"}

    update_id = body.get("update_id")
    if not should_process_update(update_id):
        return {"status": "duplicate_ignored"}

    callback_query = body.get("callback_query")
    if callback_query:
        callback_id = callback_query.get("id")
        data = callback_query.get("data", "")
        message = callback_query.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")

        if not callback_id or not chat_id or not data:
            return {"status": "ignored"}

        if data.startswith("review:"):
            try:
                answer_callback_query(
                    callback_query_id=callback_id,
                    text="Processing your review action...",
                )
            except TelegramError as exc:
                print(f"[TELEGRAM REVIEW ACK ERROR] {exc}")

            executor.submit(_process_review_callback, callback_query)
            return {"status": "accepted"}

        if ":" not in data:
            return {"status": "ignored"}

        try:
            action, asset_id_raw = data.split(":", 1)
            asset_id = int(asset_id_raw)
        except Exception:
            return {"status": "ignored"}

        try:
            answer_callback_query(
                callback_query_id=callback_id,
                text="Processing your request...",
            )
        except TelegramError as exc:
            print(f"[TELEGRAM CALLBACK ACK ERROR] {exc}")

        if action == "approve":
            try:
                send_telegram_message(
                    chat_id=chat_id,
                    text=f"🚀 Publishing asset {asset_id} now...",
                )
            except TelegramError as exc:
                print(f"[TELEGRAM PRE-PUBLISH SEND ERROR] {exc}")

            executor.submit(_process_callback_action, chat_id, action, asset_id)
            return {"status": "accepted"}

        if action == "reject":
            executor.submit(_process_callback_action, chat_id, action, asset_id)
            return {"status": "accepted"}

        return {"status": "ignored"}

    message = body.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text")
    caption = message.get("caption")
    photo = message.get("photo") or []

    if not chat_id:
        return {"status": "ignored"}

    if photo:
        try:
            store_result = store_telegram_photo_for_chat(db=db, message=message)
            print(f"[TELEGRAM PHOTO STORED] {store_result}")
        except TelegramMediaError as exc:
            print(f"[TELEGRAM PHOTO STORE ERROR] {exc}")
            try:
                send_telegram_message(
                    chat_id=chat_id,
                    text=f"❌ Failed to save uploaded image: {exc}",
                )
            except TelegramError as send_exc:
                print(f"[TELEGRAM PHOTO ERROR SEND FAILURE] {send_exc}")
            return {"status": "error", "detail": str(exc)}

        text = text or caption
        if not text:
            ack_text = (
                "✅ Image saved for this chat.\n\n"
                "Now run:\n"
                "- higgsfield\n"
                "- higgsfield image\n"
                "- higgsfield guided: <prompt>\n"
                "- higgsfield image exact: <prompt>\n"
                "- higgsfield image guided: <prompt>"
            )
            try:
                send_telegram_message(chat_id=chat_id, text=ack_text)
            except TelegramError as exc:
                print(f"[TELEGRAM PHOTO ACK ERROR] {exc}")
                return {"status": "error", "detail": str(exc)}

            return {
                "status": "ok",
                "response": ack_text,
            }

        try:
            send_telegram_message(
                chat_id=chat_id,
                text="✅ Image saved. Processing your command now...",
            )
        except TelegramError as exc:
            print(f"[TELEGRAM PHOTO+COMMAND ACK ERROR] {exc}")

    if not text:
        return {"status": "ignored"}

    print(f"[TELEGRAM MESSAGE] {text}")

    edit_result = None
    try:
        edit_result = handle_pending_edit_reply(db=db, message={"chat": chat, "text": text})
    except Exception as exc:
        print(f"[TELEGRAM EDIT CHECK ERROR] {exc}")

    if edit_result and edit_result.get("handled"):
        if edit_result.get("result"):
            try:
                _send_result_to_telegram(chat_id=chat_id, result=edit_result["result"])
            except Exception as exc:
                print(f"[TELEGRAM EDIT RESULT SEND ERROR] {exc}")
                try:
                    send_telegram_message(
                        chat_id=chat_id,
                        text=f"❌ Failed to send edited draft preview: {exc}",
                    )
                except Exception as send_exc:
                    print(f"[TELEGRAM EDIT FALLBACK SEND ERROR] {send_exc}")

        return {
            "status": "accepted",
            "response": "edit_processed",
            "detail": edit_result,
        }

    try:
        result = handle_telegram_command(text, db, chat_id=chat_id)
    except TelegramAgentError as exc:
        error_message = f"❌ {exc}"
        print(f"[TELEGRAM COMMAND ERROR] {exc}")
        try:
            send_telegram_message(chat_id=chat_id, text=error_message)
        except TelegramError as send_exc:
            print(f"[TELEGRAM SEND ERROR] {send_exc}")
        return {"status": "error", "detail": str(exc)}

    mode = result.get("mode")

    if mode == "instant":
        response_text = result["message"]
        print(f"[TELEGRAM RESPONSE] {response_text}")

        try:
            send_telegram_message(chat_id=chat_id, text=response_text)
        except TelegramError as exc:
            print(f"[TELEGRAM SEND ERROR] {exc}")
            return {
                "status": "error",
                "detail": str(exc),
                "response": response_text,
            }

        return {
            "status": "ok",
            "response": response_text,
        }

    if mode == "deferred":
        ack_message = result["ack_message"]
        workflow = result["workflow"]

        print(f"[TELEGRAM ACK] {ack_message}")

        try:
            send_telegram_message(chat_id=chat_id, text=ack_message)
        except TelegramError as exc:
            print(f"[TELEGRAM ACK SEND ERROR] {exc}")
            return {
                "status": "error",
                "detail": str(exc),
                "response": ack_message,
            }

        executor.submit(_process_deferred_workflow, chat_id, workflow)

        return {
            "status": "accepted",
            "response": ack_message,
        }

    if mode == "edited_draft_ready":
        try:
            _send_result_to_telegram(chat_id=chat_id, result=result)
        except Exception as exc:
            print(f"[TELEGRAM EDITED DRAFT SEND ERROR] {exc}")
            try:
                send_telegram_message(
                    chat_id=chat_id,
                    text=f"❌ Failed to send edited draft preview: {exc}",
                )
            except TelegramError as send_exc:
                print(f"[TELEGRAM EDITED DRAFT FALLBACK SEND ERROR] {send_exc}")

        return {
            "status": "accepted",
            "response": "edited_draft_ready",
        }

    fallback_message = "🤖 I couldn’t process that request."
    try:
        send_telegram_message(chat_id=chat_id, text=fallback_message)
    except TelegramError as exc:
        print(f"[TELEGRAM FALLBACK SEND ERROR] {exc}")

    return {
        "status": "error",
        "response": fallback_message,
    }
