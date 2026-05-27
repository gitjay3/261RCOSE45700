"""DetectionRepository 통합 테스트 — 실 PostgreSQL 사용 (Story 3-4).

PostgreSQL이 떠있지 않으면 자동 skip (`requires_pg`).
"""

from __future__ import annotations

import pytest

from detection.src.repository.detection_repository import DetectionRepository
from detection.tests.conftest import requires_pg
from shared.interfaces.llm import LLMResponse
from shared.models.crawl_event import CrawlEvent


def _build_event(post_id: str = "test_001", language: str = "ko") -> CrawlEvent:
    return CrawlEvent(
        post_id=post_id,
        source_id="ptt_lineage",
        site_name="PTT Lineage",
        raw_text="리니지M 핵 팝니다",
        language=language,
        detected_at="2026-05-27T00:00:00Z",
        correlation_id=f"cid-{post_id}",
    )


def _build_response(type_: str = "핵_치트", confidence: float = 0.95) -> LLMResponse:
    return LLMResponse(
        type=type_,
        confidence=confidence,
        reason_ko="이미지에 핵 광고 텍스트 확인됨",
        translated_text_ko=None,
        image_observed=False,
        input_tokens=537,
        output_tokens=63,
        cost_usd=0.00197,
    )


@requires_pg
def test_save_creates_sources_posts_detections(clean_db) -> None:
    repo = DetectionRepository(clean_db)
    event = _build_event()
    response = _build_response()

    detection_id = repo.save(event, response, tier="T1", model_version="openai:gpt-4o:2024-08-06")

    assert detection_id is not None and detection_id > 0

    # DB 직접 확인 — 3개 테이블에 row 들어갔는지.
    with clean_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT site_name, board_name FROM sources WHERE site_name=%s", (event.source_id,))
            source = cur.fetchone()
            assert source == ("ptt_lineage", "PTT Lineage")

            cur.execute("SELECT body, language FROM posts WHERE post_id_at_source=%s", (event.post_id,))
            post = cur.fetchone()
            assert post == ("리니지M 핵 팝니다", "ko")

            cur.execute(
                "SELECT type, tier, confidence, is_illegal, translated_text, image_observed, cost_usd, model_version "
                "FROM detections WHERE id=%s",
                (detection_id,),
            )
            det = cur.fetchone()
            assert det[0] == "핵_치트"
            assert det[1] == "T1"
            assert float(det[2]) == 0.95
            assert det[3] is True  # is_illegal (T1)
            assert det[4] is None  # translated_text_ko None
            assert det[5] is False  # image_observed
            assert float(det[6]) == pytest.approx(0.00197, rel=1e-3)
            assert det[7] == "openai:gpt-4o:2024-08-06"


@requires_pg
def test_save_t4_marks_is_illegal_false(clean_db) -> None:
    repo = DetectionRepository(clean_db)
    event = _build_event(post_id="clean_001")
    response = _build_response(type_="기타", confidence=0.85)

    detection_id = repo.save(event, response, tier="T4", model_version="openai:gpt-4o:2024-08-06")

    with clean_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_illegal, tier FROM detections WHERE id=%s", (detection_id,))
            is_illegal, tier = cur.fetchone()
            assert is_illegal is False
            assert tier == "T4"


@requires_pg
def test_save_is_idempotent_on_same_model_version(clean_db) -> None:
    """동일 post_id + 동일 model_version으로 2회 save → 두 번째는 None 반환."""
    repo = DetectionRepository(clean_db)
    event = _build_event(post_id="dup_001")
    response = _build_response()

    first_id = repo.save(event, response, tier="T1", model_version="openai:gpt-4o:2024-08-06")
    second_id = repo.save(event, response, tier="T1", model_version="openai:gpt-4o:2024-08-06")

    assert first_id is not None
    assert second_id is None  # ON CONFLICT DO NOTHING → RETURNING 없음

    # detections에는 1 row만.
    with clean_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM detections "
                "WHERE post_id IN (SELECT id FROM posts WHERE post_id_at_source=%s)",
                (event.post_id,),
            )
            assert cur.fetchone()[0] == 1


@requires_pg
def test_save_different_model_version_allowed(clean_db) -> None:
    """동일 post_id + 다른 model_version → 두 번째도 INSERT 성공."""
    repo = DetectionRepository(clean_db)
    event = _build_event(post_id="multimodel_001")
    response = _build_response()

    id1 = repo.save(event, response, tier="T1", model_version="openai:gpt-4o:2024-08-06")
    id2 = repo.save(event, response, tier="T1", model_version="openai:gpt-4o-mini:2024-07-18")

    assert id1 is not None and id2 is not None
    assert id1 != id2

    with clean_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM detections")
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT COUNT(*) FROM posts")
            assert cur.fetchone()[0] == 1  # posts는 1 row만 (UPSERT)


@requires_pg
def test_save_translated_text_persisted(clean_db) -> None:
    repo = DetectionRepository(clean_db)
    event = _build_event(post_id="zh_001", language="zh-CN")
    response = _build_response()
    response.translated_text_ko = "월핵 최신 버전 업로드. 탐지 안 됨. 무료"

    detection_id = repo.save(event, response, tier="T1", model_version="openai:gpt-4o:2024-08-06")

    with clean_db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT translated_text FROM detections WHERE id=%s", (detection_id,))
            assert cur.fetchone()[0] == "월핵 최신 버전 업로드. 탐지 안 됨. 무료"
