from typing import Any

import boto3
from botocore.config import Config

from app.config import settings


class S3Error(Exception):
    """Raised when an S3 operation fails."""


s3_client = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    endpoint_url=f"https://s3.{settings.AWS_REGION}.amazonaws.com",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
    ),
)


def generate_presigned_get_url(
    bucket: str,
    key: str,
    expires_in: int = 3600,
) -> str:
    """
    Generate a temporary presigned URL for reading a private S3 object.
    Useful when third-party providers like Higgsfield need temporary access.
    """
    if not bucket:
        raise S3Error("S3 bucket is required")
    if not key:
        raise S3Error("S3 object key is required")

    try:
        return s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception as exc:
        raise S3Error(
            f"Failed to generate presigned GET URL for s3://{bucket}/{key}"
        ) from exc


def upload_file_to_s3(
    file_path: str,
    object_key: str,
    content_type: str | None = None,
) -> dict[str, Any]:
    """
    Upload a local file to S3 and return normalized metadata.
    """
    if not settings.S3_BUCKET_NAME:
        raise S3Error("Missing S3_BUCKET_NAME")
    if not file_path:
        raise S3Error("file_path is required")
    if not object_key:
        raise S3Error("object_key is required")

    extra_args: dict[str, str] = {}
    if content_type:
        extra_args["ContentType"] = content_type

    try:
        if extra_args:
            s3_client.upload_file(
                Filename=file_path,
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_key,
                ExtraArgs=extra_args,
            )
        else:
            s3_client.upload_file(
                Filename=file_path,
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_key,
            )

        return {
            "bucket": settings.S3_BUCKET_NAME,
            "key": object_key,
            "url": build_s3_object_url(
                bucket=settings.S3_BUCKET_NAME,
                key=object_key,
            ),
        }

    except Exception as exc:
        raise S3Error(
            f"Failed to upload file to s3://{settings.S3_BUCKET_NAME}/{object_key}"
        ) from exc


def build_s3_object_url(bucket: str, key: str) -> str:
    """
    Build the regional HTTPS URL for an S3 object.
    """
    if not bucket:
        raise S3Error("S3 bucket is required")
    if not key:
        raise S3Error("S3 object key is required")

    return f"https://{bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


def head_object(bucket: str, key: str) -> dict[str, Any]:
    """
    Fetch metadata for an S3 object.
    Helpful for validation, debugging, and future automation checks.
    """
    if not bucket:
        raise S3Error("S3 bucket is required")
    if not key:
        raise S3Error("S3 object key is required")

    try:
        return s3_client.head_object(Bucket=bucket, Key=key)
    except Exception as exc:
        raise S3Error(f"Failed to head object s3://{bucket}/{key}") from exc
