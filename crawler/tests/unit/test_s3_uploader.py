"""Story 2.4 — S3Uploader 및 PostStorage S3 통합 단위 테스트 (실제 boto3 호출 0건)."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import botocore.exceptions
import pytest

from crawler.src.s3_uploader import S3Uploader
from crawler.src.storage import PostStorage, StorageResult
from crawler.src.crawl4ai_crawler import CrawlResult
from shared.models.crawl_event import CrawlEvent


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_uploader(bucket: str = "test-bucket") -> tuple[S3Uploader, MagicMock]:
    """boto3를 mock한 S3Uploader 인스턴스 반환."""
    with patch("crawler.src.s3_uploader.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        uploader = S3Uploader(bucket)
    return uploader, mock_client


def _client_error(code: str = "NoSuchBucket") -> botocore.exceptions.ClientError:
    return botocore.exceptions.ClientError(
        {"Error": {"Code": code, "Message": ""}}, "PutObject"
    )


# ---------------------------------------------------------------------------
# S3Uploader — upload_text
# ---------------------------------------------------------------------------

class TestUploadText:
    def test_upload_text_calls_put_object(self):
        uploader, mock_client = _make_uploader()
        with patch.object(uploader, "_client", mock_client):
            uploader.upload_text(
                "내용",
                site="inven_maple",
                date="2026-04-28",
                post_id="220821",
                correlation_id="cid-1",
            )
        mock_client.put_object.assert_called_once()

    def test_upload_text_correct_s3_key_format(self):
        uploader, mock_client = _make_uploader()
        with patch.object(uploader, "_client", mock_client):
            uri = uploader.upload_text(
                "텍스트 내용",
                site="inven_maple",
                date="2026-04-28",
                post_id="220821",
                correlation_id="cid-1",
            )
        assert uri == "s3://test-bucket/raw/inven_maple/2026-04-28/220821.md"
        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="raw/inven_maple/2026-04-28/220821.md",
            Body="텍스트 내용".encode("utf-8"),
            ContentType="text/markdown; charset=utf-8",
        )

    def test_upload_text_returns_s3_uri(self):
        uploader, mock_client = _make_uploader(bucket="my-bucket")
        with patch.object(uploader, "_client", mock_client):
            uri = uploader.upload_text(
                "x", site="site", date="2026-01-01", post_id="p1", correlation_id="c"
            )
        assert uri.startswith("s3://my-bucket/raw/")
        assert uri.endswith("/p1.md")

    def test_upload_text_client_error_raises(self):
        uploader, mock_client = _make_uploader()
        mock_client.put_object.side_effect = _client_error()
        with patch.object(uploader, "_client", mock_client):
            with pytest.raises(botocore.exceptions.ClientError):
                uploader.upload_text(
                    "text", site="s", date="2026-04-28", post_id="1", correlation_id="c"
                )


# ---------------------------------------------------------------------------
# S3Uploader — upload_images
# ---------------------------------------------------------------------------

class TestUploadImages:
    def test_upload_images_correct_key_format(self, tmp_path):
        uploader, mock_client = _make_uploader()
        img = tmp_path / "img_000.jpg"
        img.write_bytes(b"data")
        with patch.object(uploader, "_client", mock_client):
            uris = uploader.upload_images(
                [img], site="inven_maple", date="2026-04-28", post_id="220821", correlation_id="c"
            )
        assert len(uris) == 1
        assert uris[0] == "s3://test-bucket/images/inven_maple/2026-04-28/220821/img_000.jpg"

    def test_upload_images_returns_uri_list(self, tmp_path):
        uploader, mock_client = _make_uploader()
        imgs = []
        for i in range(3):
            p = tmp_path / f"img_{i:03d}.jpg"
            p.write_bytes(b"data")
            imgs.append(p)
        with patch.object(uploader, "_client", mock_client):
            uris = uploader.upload_images(
                imgs, site="s", date="2026-04-28", post_id="p", correlation_id="c"
            )
        assert len(uris) == 3

    def test_upload_images_individual_failure_continues(self, tmp_path):
        uploader, mock_client = _make_uploader()
        img1 = tmp_path / "img_000.jpg"
        img1.write_bytes(b"data1")
        img2 = tmp_path / "img_001.jpg"
        img2.write_bytes(b"data2")

        def side_effect(**kwargs):
            if "img_000" in kwargs["Key"]:
                raise _client_error("403")

        mock_client.put_object.side_effect = side_effect
        with patch.object(uploader, "_client", mock_client):
            uris = uploader.upload_images(
                [img1, img2], site="s", date="2026-04-28", post_id="1", correlation_id="c"
            )
        assert len(uris) == 1
        assert "img_001" in uris[0]

    def test_upload_images_all_fail_returns_empty_list(self, tmp_path):
        uploader, mock_client = _make_uploader()
        img = tmp_path / "img_000.jpg"
        img.write_bytes(b"data")
        mock_client.put_object.side_effect = _client_error()
        with patch.object(uploader, "_client", mock_client):
            uris = uploader.upload_images(
                [img], site="s", date="2026-04-28", post_id="1", correlation_id="c"
            )
        assert uris == []

    def test_upload_images_empty_list_returns_empty(self):
        uploader, mock_client = _make_uploader()
        with patch.object(uploader, "_client", mock_client):
            uris = uploader.upload_images(
                [], site="s", date="2026-04-28", post_id="1", correlation_id="c"
            )
        assert uris == []
        mock_client.put_object.assert_not_called()


# ---------------------------------------------------------------------------
# S3Uploader — IAM Role 패턴 (자격증명 하드코딩 금지)
# ---------------------------------------------------------------------------

class TestS3UploaderInit:
    def test_s3_uploader_no_hardcoded_credentials(self):
        with patch("crawler.src.s3_uploader.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            S3Uploader("bucket")
        call_kwargs = mock_boto3.client.call_args.kwargs
        assert "aws_access_key_id" not in call_kwargs
        assert "aws_secret_access_key" not in call_kwargs

    def test_s3_uploader_uses_aws_region_env(self):
        with patch.dict(os.environ, {"AWS_REGION": "ap-northeast-2"}):
            with patch("crawler.src.s3_uploader.boto3") as mock_boto3:
                mock_boto3.client.return_value = MagicMock()
                S3Uploader("bucket")
        call_kwargs = mock_boto3.client.call_args.kwargs
        assert call_kwargs.get("region_name") == "ap-northeast-2"

    def test_s3_uploader_no_region_env_omits_region(self):
        env = {k: v for k, v in os.environ.items() if k != "AWS_REGION"}
        with patch.dict(os.environ, env, clear=True):
            with patch("crawler.src.s3_uploader.boto3") as mock_boto3:
                mock_boto3.client.return_value = MagicMock()
                S3Uploader("bucket")
        call_kwargs = mock_boto3.client.call_args.kwargs
        assert "region_name" not in call_kwargs


# ---------------------------------------------------------------------------
# PostStorage — S3 통합
# ---------------------------------------------------------------------------

class TestPostStorageS3:
    def _make_crawl_result(self) -> CrawlResult:
        return CrawlResult(
            url="https://example.com",
            raw_markdown="raw",
            fit_markdown="fit content",
            images=[],
            downloaded_images=[],
        )

    def test_post_storage_s3_enabled_calls_uploader(self, tmp_path):
        mock_uploader = MagicMock()
        mock_uploader.upload_text.return_value = "s3://bucket/raw/inven_maple/2026-04-28/123.md"
        mock_uploader.upload_images.return_value = []

        with patch.dict(os.environ, {"ENABLE_S3_UPLOAD": "true", "S3_BUCKET_NAME": "bucket"}):
            with patch("crawler.src.storage.S3Uploader", return_value=mock_uploader):
                storage = PostStorage(base_dir=str(tmp_path))
                result = storage.save(
                    site_id="inven_maple",
                    post_id="123",
                    url="https://example.com",
                    result=self._make_crawl_result(),
                    correlation_id="cid-1",
                )

        assert result.s3_text_path == "s3://bucket/raw/inven_maple/2026-04-28/123.md"
        mock_uploader.upload_text.assert_called_once()
        mock_uploader.upload_images.assert_called_once()

    def test_post_storage_s3_disabled_no_s3_call(self, tmp_path):
        mock_uploader = MagicMock()

        with patch.dict(os.environ, {"ENABLE_S3_UPLOAD": "false"}):
            with patch("crawler.src.storage.S3Uploader", return_value=mock_uploader) as mock_cls:
                storage = PostStorage(base_dir=str(tmp_path))
                result = storage.save(
                    site_id="site",
                    post_id="999",
                    url="https://example.com",
                    result=self._make_crawl_result(),
                )

        mock_cls.assert_not_called()
        assert result.s3_text_path == ""
        assert result.s3_image_paths == []

    def test_post_storage_s3_default_disabled(self, tmp_path):
        """ENABLE_S3_UPLOAD 미설정 시 S3 업로드 없음."""
        env = {k: v for k, v in os.environ.items() if k != "ENABLE_S3_UPLOAD"}
        with patch.dict(os.environ, env, clear=True):
            with patch("crawler.src.storage.S3Uploader") as mock_cls:
                storage = PostStorage(base_dir=str(tmp_path))
                result = storage.save(
                    site_id="site",
                    post_id="abc",
                    url="https://example.com",
                    result=self._make_crawl_result(),
                )

        mock_cls.assert_not_called()
        assert result.s3_text_path == ""

    def test_post_storage_s3_enabled_no_bucket_raises(self):
        """ENABLE_S3_UPLOAD=true지만 S3_BUCKET_NAME 없으면 ValueError."""
        env = {k: v for k, v in os.environ.items() if k != "S3_BUCKET_NAME"}
        env["ENABLE_S3_UPLOAD"] = "true"
        with patch("crawler.src.storage.S3Uploader"):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
                    PostStorage()

    def test_post_storage_returns_storage_result(self, tmp_path):
        with patch.dict(os.environ, {"ENABLE_S3_UPLOAD": "false"}):
            storage = PostStorage(base_dir=str(tmp_path))
            result = storage.save(
                site_id="site",
                post_id="p1",
                url="https://example.com",
                result=self._make_crawl_result(),
            )
        assert isinstance(result, StorageResult)
        assert result.local_path.exists()


# ---------------------------------------------------------------------------
# CrawlEvent — s3 필드 하위 호환
# ---------------------------------------------------------------------------

class TestCrawlEventS3Fields:
    _BASE_PAYLOAD = {
        "post_id": "123",
        "source_id": "src",
        "site_name": "inven_maple",
        "raw_text": "텍스트",
        "language": "ko",
        "detected_at": "2026-04-28T00:00:00Z",
        "correlation_id": "cid-1",
    }

    def test_crawl_event_s3_paths_roundtrip(self):
        event = CrawlEvent(
            **self._BASE_PAYLOAD,
            s3_text_path="s3://bucket/raw/site/2026-04-28/123.md",
            s3_image_paths=["s3://bucket/images/site/2026-04-28/123/img_000.jpg"],
        )
        restored = CrawlEvent.from_json(event.to_json())
        assert restored.s3_text_path == "s3://bucket/raw/site/2026-04-28/123.md"
        assert restored.s3_image_paths == ["s3://bucket/images/site/2026-04-28/123/img_000.jpg"]

    def test_crawl_event_backward_compat_no_s3_fields(self):
        """s3 필드 없는 기존 JSON도 from_json() 성공."""
        data = json.dumps(self._BASE_PAYLOAD)
        event = CrawlEvent.from_json(data)
        assert event.s3_text_path == ""
        assert event.s3_image_paths == []

    def test_crawl_event_s3_text_path_default_empty_string(self):
        event = CrawlEvent(**self._BASE_PAYLOAD)
        assert event.s3_text_path == ""

    def test_crawl_event_s3_image_paths_default_empty_list(self):
        event = CrawlEvent(**self._BASE_PAYLOAD)
        assert event.s3_image_paths == []
