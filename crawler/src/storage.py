"""포스트 단위 저장 모듈.

output/posts/{site_id}/{post_id}/
    post.json   ← 텍스트 + 이미지 메타데이터
    img_001.jpg ← 사용자 업로드 이미지
    img_002.png
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.crawler import CrawlResult
from src.s3_uploader import S3Uploader


@dataclass
class StorageResult:
    local_path: Path
    s3_text_path: str = ""
    s3_image_paths: list[str] = field(default_factory=list)


class PostStorage:
    def __init__(self, base_dir: str = "output/posts") -> None:
        self._base = Path(base_dir)
        enable_s3 = os.environ.get("ENABLE_S3_UPLOAD", "false").lower() == "true"
        if enable_s3:
            bucket = os.environ.get("S3_BUCKET_NAME")
            if not bucket:
                raise ValueError("S3_BUCKET_NAME is required when ENABLE_S3_UPLOAD=true")
            self._s3_uploader: S3Uploader | None = S3Uploader(bucket)
        else:
            self._s3_uploader = None

    def save(
        self,
        *,
        site_id: str,
        post_id: str,
        url: str,
        result: CrawlResult,
        correlation_id: str = "",
    ) -> StorageResult:
        """포스트 데이터를 디스크에 저장하고 StorageResult를 반환."""
        post_dir = self._base / site_id / post_id
        post_dir.mkdir(parents=True, exist_ok=True)

        # 이미지 파일을 포스트 디렉터리로 이동
        image_records: list[dict] = []
        for img_meta, src_path in zip(result.images, result.downloaded_images):
            dest = post_dir / src_path.name
            dest.write_bytes(src_path.read_bytes())
            src_path.unlink(missing_ok=True)    # 임시 파일 삭제
            image_records.append({
                "filename": dest.name,
                "src": img_meta.get("src", ""),
                "alt": img_meta.get("alt", ""),
                "score": img_meta.get("score", 0),
            })

        # post.json 저장
        post_data = {
            "post_id": post_id,
            "site": site_id,
            "url": url,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "text": result.markdown,
            "images": image_records,
        }
        (post_dir / "post.json").write_text(
            json.dumps(post_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        s3_text_path = ""
        s3_image_paths: list[str] = []
        if self._s3_uploader is not None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            s3_text_path = self._s3_uploader.upload_text(
                result.markdown,
                site=site_id,
                date=date_str,
                post_id=post_id,
                correlation_id=correlation_id,
            )
            local_img_paths = [post_dir / r["filename"] for r in image_records]
            s3_image_paths = self._s3_uploader.upload_images(
                local_img_paths,
                site=site_id,
                date=date_str,
                post_id=post_id,
                correlation_id=correlation_id,
            )

        return StorageResult(
            local_path=post_dir,
            s3_text_path=s3_text_path,
            s3_image_paths=s3_image_paths,
        )
