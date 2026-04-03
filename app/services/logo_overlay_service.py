import io
from pathlib import Path

import boto3
from PIL import Image

from app.config import settings


class LogoOverlayError(Exception):
    pass


def _download_logo_bytes_from_s3(logo_s3_key: str) -> bytes:
    if not logo_s3_key:
        raise LogoOverlayError("logo_s3_key is required")

    s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
    response = s3_client.get_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=logo_s3_key,
    )
    body = response.get("Body")
    if body is None:
        raise LogoOverlayError(f"Could not download logo from S3 key: {logo_s3_key}")

    return body.read()


def apply_logo_overlay_to_local_image(
    local_image_path: str,
    logo_s3_key: str,
    *,
    padding_px: int = 24,
    max_logo_width_ratio: float = 0.18,
    opacity: float = 0.95,
) -> str:
    if not logo_s3_key:
        return local_image_path

    try:
        base_image = Image.open(local_image_path).convert("RGBA")
    except Exception as exc:
        raise LogoOverlayError(f"Failed to open base image for logo overlay: {exc}") from exc

    try:
        logo_bytes = _download_logo_bytes_from_s3(logo_s3_key)
        logo_image = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
    except Exception as exc:
        raise LogoOverlayError(f"Failed to load logo image: {exc}") from exc

    max_logo_width = max(1, int(base_image.width * max_logo_width_ratio))
    if logo_image.width > max_logo_width:
        resize_ratio = max_logo_width / float(logo_image.width)
        resized_height = max(1, int(logo_image.height * resize_ratio))
        logo_image = logo_image.resize((max_logo_width, resized_height), Image.LANCZOS)

    if 0 < opacity < 1:
        alpha = logo_image.getchannel("A")
        alpha = alpha.point(lambda p: int(p * opacity))
        logo_image.putalpha(alpha)

    x = max(padding_px, base_image.width - logo_image.width - padding_px)
    y = max(padding_px, base_image.height - logo_image.height - padding_px)

    composited = base_image.copy()
    composited.paste(logo_image, (x, y), logo_image)

    output_format = (Image.open(local_image_path).format or "").upper()
    if output_format in {"JPEG", "JPG"}:
        composited = composited.convert("RGB")
        composited.save(local_image_path, format="JPEG", quality=95)
    else:
        ext = Path(local_image_path).suffix.lower()
        if ext in {".jpg", ".jpeg"}:
            composited = composited.convert("RGB")
            composited.save(local_image_path, format="JPEG", quality=95)
        else:
            composited.save(local_image_path, format="PNG")

    return local_image_path
