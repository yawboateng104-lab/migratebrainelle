import threading
import time


_UPDATE_LOCK = threading.Lock()
_PROCESSED_UPDATES: dict[int, float] = {}

_CHAT_LOCK = threading.Lock()
_CHAT_INFLIGHT: dict[int | str, dict] = {}

_TTL_SECONDS = 60 * 30


def _cleanup_processed_updates() -> None:
    now = time.time()
    expired = [k for k, ts in _PROCESSED_UPDATES.items() if now - ts > _TTL_SECONDS]
    for k in expired:
        _PROCESSED_UPDATES.pop(k, None)


def should_process_update(update_id: int | None) -> bool:
    if update_id is None:
        return True

    with _UPDATE_LOCK:
        _cleanup_processed_updates()

        if update_id in _PROCESSED_UPDATES:
            return False

        _PROCESSED_UPDATES[update_id] = time.time()
        return True


def start_chat_job(chat_id: int | str, workflow: str) -> bool:
    with _CHAT_LOCK:
        active = _CHAT_INFLIGHT.get(chat_id)
        if active and active.get("active"):
            return False

        _CHAT_INFLIGHT[chat_id] = {
            "active": True,
            "workflow": workflow,
            "pending_asset_id": active.get("pending_asset_id") if active else None,
            "active_campaign_id": active.get("active_campaign_id") if active else None,
        }
        return True


def finish_chat_job(chat_id: int | str) -> None:
    with _CHAT_LOCK:
        active = _CHAT_INFLIGHT.get(chat_id)
        if not active:
            return

        active["active"] = False
        _CHAT_INFLIGHT[chat_id] = active


def is_chat_busy(chat_id: int | str) -> bool:
    with _CHAT_LOCK:
        active = _CHAT_INFLIGHT.get(chat_id)
        return bool(active and active.get("active"))


def set_pending_asset_id(chat_id: int | str, asset_id: int) -> None:
    with _CHAT_LOCK:
        active = _CHAT_INFLIGHT.get(chat_id, {})
        active["pending_asset_id"] = asset_id
        if "active" not in active:
            active["active"] = False
        _CHAT_INFLIGHT[chat_id] = active


def get_pending_asset_id(chat_id: int | str) -> int | None:
    with _CHAT_LOCK:
        active = _CHAT_INFLIGHT.get(chat_id)
        if not active:
            return None
        return active.get("pending_asset_id")


def set_active_campaign(chat_id: int | str, campaign_id: int) -> None:
    with _CHAT_LOCK:
        active = _CHAT_INFLIGHT.get(chat_id, {})
        active["active_campaign_id"] = campaign_id
        if "active" not in active:
            active["active"] = False
        _CHAT_INFLIGHT[chat_id] = active


def get_active_campaign(chat_id: int | str) -> int | None:
    with _CHAT_LOCK:
        active = _CHAT_INFLIGHT.get(chat_id)
        if not active:
            return None
        return active.get("active_campaign_id")
