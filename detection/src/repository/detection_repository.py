"""Detection Repository — posts UPSERT + detections INSERT 1 트랜잭션 (Story 3-4).

흐름:
  1. sources(site_name) UPSERT → sources.id 회수
  2. posts(source_id, post_id_at_source) UPSERT → posts.id 회수
  3. detections(post_id, model_version) INSERT — V3 unique constraint으로 멱등성
     - ON CONFLICT (post_id, model_version) DO NOTHING

본 레포는 write 전용 (`save` 단일 public 메서드). read는 Spring API 레이어 전담.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from psycopg_pool import ConnectionPool

from shared.interfaces.llm import LLMResponse
from shared.models.crawl_event import CrawlEvent
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_logger = get_logger(__name__)


def _parse_crawled_at(value: str) -> datetime:
    """CrawlEvent.detected_at(ISO 8601 문자열) → datetime. 'Z' 접미사 지원."""
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(timezone.utc)


class DetectionRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def save(
        self,
        event: CrawlEvent,
        response: LLMResponse,
        tier: str,
        model_version: str,
    ) -> int | None:
        """posts + detections 저장. detections.id 반환 (멱등 conflict 시 None).

        한 트랜잭션:
          - sources UPSERT (site_name=event.source_id, board_name=event.site_name)
          - posts UPSERT (source_id, post_id_at_source=event.post_id, body=raw_text, ...)
          - detections INSERT (post_id, tier, type, confidence, ..., model_version)
              ON CONFLICT (post_id, model_version) DO NOTHING

        Raises:
            psycopg.Error: 연결/SQL 실패. 호출자(RetryHandler 밖)가 catch.
        """
        crawled_at = _parse_crawled_at(event.detected_at)
        token_usage_json = json.dumps({
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        })
        is_illegal = tier != "T4"  # 사업 정의: T4 = 정상 / T1~T3 = 위반

        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                # 1) sources UPSERT — site_name unique
                cur.execute(
                    """
                    INSERT INTO sources (site_name, board_name)
                    VALUES (%s, %s)
                    ON CONFLICT (site_name) DO UPDATE
                        SET board_name = COALESCE(sources.board_name, EXCLUDED.board_name)
                    RETURNING id
                    """,
                    (event.source_id, event.site_name),
                )
                source_row = cur.fetchone()
                if source_row is None:
                    raise RuntimeError(f"sources UPSERT 실패: site_name={event.source_id}")
                source_id = source_row[0]

                # 2) posts UPSERT — (source_id, post_id_at_source) unique
                # post_url: 비어 있으면 None 전달 — 기존 URL이 있을 경우 덮지 않음 (COALESCE).
                post_url_value = event.post_url if event.post_url else None
                cur.execute(
                    """
                    INSERT INTO posts (
                        source_id, post_id_at_source, body, language, crawled_at, post_url
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id, post_id_at_source) DO UPDATE
                        SET body = EXCLUDED.body,
                            language = EXCLUDED.language,
                            post_url = COALESCE(EXCLUDED.post_url, posts.post_url)
                    RETURNING id
                    """,
                    (
                        source_id,
                        event.post_id,
                        event.raw_text,
                        event.language,
                        crawled_at,
                        post_url_value,
                    ),
                )
                post_row = cur.fetchone()
                if post_row is None:
                    raise RuntimeError(
                        f"posts UPSERT 실패: post_id_at_source={event.post_id}"
                    )
                post_id = post_row[0]

                # 3) detections INSERT — (post_id, model_version) unique 멱등성
                cur.execute(
                    """
                    INSERT INTO detections (
                        post_id, is_illegal, type, tier, confidence, reason,
                        translated_text, image_observed, token_usage_json,
                        cost_usd, model_version, detected_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
                    ON CONFLICT (post_id, model_version) DO NOTHING
                    RETURNING id
                    """,
                    (
                        post_id,
                        is_illegal,
                        response.type,
                        tier,
                        response.confidence,
                        response.reason_ko,
                        response.translated_text_ko,
                        response.image_observed,
                        token_usage_json,
                        response.cost_usd,
                        model_version,
                    ),
                )
                det_row = cur.fetchone()
                detection_id = det_row[0] if det_row else None

        if detection_id is None:
            _logger.info(
                "detection 멱등 skip — 이미 저장됨 (post_id=%s, model_version=%s)",
                event.post_id, model_version,
                extra={
                    "correlation_id": event.correlation_id,
                    "service": _SERVICE_NAME,
                    "post_id": event.post_id,
                    "model_version": model_version,
                },
            )
        else:
            _logger.info(
                "detection saved — id=%d post_id=%s tier=%s",
                detection_id, event.post_id, tier,
                extra={
                    "correlation_id": event.correlation_id,
                    "service": _SERVICE_NAME,
                    "post_id": event.post_id,
                    "tier": tier,
                    "detection_id": detection_id,
                },
            )
        return detection_id
