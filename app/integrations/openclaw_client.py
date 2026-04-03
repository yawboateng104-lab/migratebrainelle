import requests

from app.config import settings


def openclaw_healthcheck() -> dict:
    if not settings.OPENCLAW_ENABLED:
        return {"enabled": False, "ok": False, "status": "disabled"}

    try:
        response = requests.get(f"{settings.OPENCLAW_BASE_URL}/health", timeout=10)
        response.raise_for_status()
        return {"enabled": True, "ok": True, "payload": response.json()}
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": str(exc)}
