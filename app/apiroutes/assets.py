from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    GenerateVideoAssetRequest,
    GenerateVideoAssetResponse,
)
from app.services.asset_generator import generate_asset_from_video_prompt
from app.integrations.higgsfield import HiggsfieldError
from app.integrations.s3 import S3Error
from app.services.asset_storage import AssetStorageError

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post(
    "/generate-video",
    response_model=GenerateVideoAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_video_asset(payload: GenerateVideoAssetRequest, db: Session = Depends(get_db)):
    try:
        asset = generate_asset_from_video_prompt(payload, db)

        return GenerateVideoAssetResponse(
            id=asset.id,
            content_idea_id=asset.content_idea_id,
            asset_type=asset.asset_type,
            asset_url=asset.asset_url,
            created_at=asset.created_at,
        )

    except HiggsfieldError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Higgsfield generation failed: {exc}",
        ) from exc

    except S3Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 operation failed: {exc}",
        ) from exc

    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Asset storage failed: {exc}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected asset generation error: {exc}",
        ) from exc
