"""
Storage service — encrypted file upload/download via MinIO (S3-compatible).
All patient genomic files are stored with AES-256 server-side encryption.
"""
import os
import socket
import uuid
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException, status

from config import settings

_s3_client = None


def _minio_reachable(endpoint: str) -> bool:
    parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 9000)
    if not host:
        return False

    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def _use_local_storage() -> bool:
    return settings.environment == "development" and not _minio_reachable(settings.minio_endpoint)


def _local_root() -> Path:
    root = Path(settings.local_storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


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
    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()

    key = f"{patient_id}/{file_type}/{uuid.uuid4()}{ext}"

    content = await file.read()

    if _use_local_storage():
        path = _local_root() / settings.bucket_raw / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    bucket = settings.bucket_raw
    _ensure_bucket(bucket)

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
    if _use_local_storage():
        path = _local_root() / bucket / key
        if not path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found.",
            )
        return f"file://{path.as_posix()}"

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
