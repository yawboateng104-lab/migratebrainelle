from app.config import settings
from app.integrations.s3 import generate_presigned_get_url


def get_source_image_url_from_s3_key(source_image_s3_key: str, expires_in: int = 3600) -> str:
    """
    Convert a private S3 object key into a temporary presigned GET URL
    that Higgsfield can access.
    """
    return generate_presigned_get_url(
        bucket=settings.S3_BUCKET_NAME,
        key=source_image_s3_key,
        expires_in=expires_in,
    )
