from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import boto3
import botocore.exceptions

from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)

_S3_FATAL_EXC = (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError)
_IMG_NONFATAL_EXC = _S3_FATAL_EXC + (OSError,)


class S3Uploader:
    def __init__(self, bucket_name: str) -> None:
        self._bucket = bucket_name
        region = os.environ.get("AWS_REGION")
        kwargs = {"region_name": region} if region else {}
        self._client = boto3.client("s3", **kwargs)

    def upload_text(
        self, text: str, *, site: str, date: str, post_id: str, correlation_id: str
    ) -> str:
        if not text:
            _logger.info(
                "S3 텍스트 업로드 skip (빈 본문): site=%s post_id=%s", site, post_id,
                extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
            )
            return ""
        key = f"raw/{site}/{date}/{post_id}.md"
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=text.encode("utf-8"),
                ContentType="text/markdown; charset=utf-8",
            )
            _logger.info(
                "S3 텍스트 업로드 완료: s3://%s/%s", self._bucket, key,
                extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
            )
        except _S3_FATAL_EXC as exc:
            _logger.error(
                "S3 텍스트 업로드 실패: %s — %s", key, exc,
                extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
            )
            raise
        return f"s3://{self._bucket}/{key}"

    def upload_images(
        self,
        image_paths: list[Path],
        *,
        site: str,
        date: str,
        post_id: str,
        correlation_id: str,
    ) -> list[str]:
        s3_uris: list[str] = []
        for path in image_paths:
            key = f"images/{site}/{date}/{post_id}/{path.name}"
            try:
                content_type, _ = mimetypes.guess_type(path.name)
                put_kwargs = {
                    "Bucket": self._bucket,
                    "Key": key,
                    "Body": path.read_bytes(),
                }
                if content_type:
                    put_kwargs["ContentType"] = content_type
                self._client.put_object(**put_kwargs)
                _logger.info(
                    "S3 이미지 업로드 완료: s3://%s/%s", self._bucket, key,
                    extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
                )
                s3_uris.append(f"s3://{self._bucket}/{key}")
            except _IMG_NONFATAL_EXC as exc:
                _logger.warning(
                    "S3 이미지 업로드 실패 (건너뜀): %s — %s", key, exc,
                    extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
                )
        return s3_uris
