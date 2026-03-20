"""
Storage service — encrypted file upload/download via MinIO (S3-compatible).
All patient genomic files are stored with AES-256 server-side encryption.
"""
import uuid
from datetime import datetime

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException, status

from config import settings

_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None:
        scheme = "https" if settings.minio_secure else "http"
        _s3_client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
    return _s3_client


def _ensure_bucket(bucket: str) -> None:
    s3 = _get_s3()
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)


async def upload_encrypted_file(
    file: UploadFile,
    patient_id: str,
    file_type: str,
) -> str:
    """
    Upload a file to MinIO with server-side AES-256 encryption.
    Returns the S3 object key.
    The key path never contains patient PII — only the anonymized patient UUID.
    """
    bucket = settings.bucket_raw
    _ensure_bucket(bucket)

    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()

    key = f"{patient_id}/{file_type}/{uuid.uuid4()}{ext}"

    content = await file.read()

    try:
        _get_s3().put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ServerSideEncryption="AES256",
            ContentType=file.content_type or "application/octet-stream",
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed. Please try again.",
        ) from exc

    return key


def generate_presigned_download_url(key: str, bucket: str, expires_in: int = 3600) -> str:
    """
    Generate a temporary pre-signed URL for a patient to download their report.
    URL expires after `expires_in` seconds (default 1 hour).
    """
    try:
        url = _get_s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate download link.",
        ) from exc
