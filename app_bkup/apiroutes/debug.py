from fastapi import APIRouter, HTTPException
from app.services.openclaw_service import _call_openclaw

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/openclaw-ping")
def openclaw_ping():
    try:
        reply = _call_openclaw('Return exactly this JSON: {"ok": true}')
        return {"raw_reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
