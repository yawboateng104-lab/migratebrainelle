import requests

from app.config import settings


class TelegramError(Exception):
    pass


def _require_bot_token() -> str:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise TelegramError("Missing TELEGRAM_BOT_TOKEN")
    return settings.TELEGRAM_BOT_TOKEN


def send_telegram_message(
    chat_id: int | str,
    text: str,
    reply_markup: dict | None = None,
) -> dict:
    token = _require_bot_token()

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    response = requests.post(url, json=payload, timeout=30)

    if response.status_code != 200:
        raise TelegramError(
            f"Telegram sendMessage failed: {response.status_code} {response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise TelegramError("Telegram returned non-JSON response") from exc


def answer_callback_query(
    callback_query_id: str,
    text: str | None = None,
    show_alert: bool = False,
) -> dict:
    token = _require_bot_token()

    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"

    payload = {
        "callback_query_id": callback_query_id,
        "show_alert": show_alert,
    }

    if text:
        payload["text"] = text

    response = requests.post(url, json=payload, timeout=30)

    if response.status_code != 200:
        raise TelegramError(
            f"Telegram answerCallbackQuery failed: {response.status_code} {response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise TelegramError("Telegram returned non-JSON response") from exc
