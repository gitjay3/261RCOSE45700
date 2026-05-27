"""pytest 공통 fixture — 실 PostgreSQL pool + 테이블 truncate (Story 3-4)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# infra/.env를 detection 테스트에서도 로드 — DB_PASSWORD 등 필요.
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = _PROJECT_ROOT / "infra" / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


def _pg_available() -> bool:
    """DB_PASSWORD 환경변수 + PostgreSQL 5432 도달 가능 여부."""
    if not os.environ.get("DB_PASSWORD"):
        return False
    try:
        import socket
        host = os.environ.get("DB_HOST", "localhost")
        port = int(os.environ.get("DB_PORT", "5432"))
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


_PG_AVAILABLE = _pg_available()
requires_pg = pytest.mark.skipif(
    not _PG_AVAILABLE,
    reason="PostgreSQL 미가동 또는 DB_PASSWORD 미설정 — Docker compose up postgres 후 재실행",
)


@pytest.fixture(scope="session")
def db_pool():
    """프로세스 전역 connection pool — session scope."""
    if not _PG_AVAILABLE:
        pytest.skip("PostgreSQL 미가동")
    from detection.src.config.db_config import get_pool, close_pool
    pool = get_pool()
    yield pool
    close_pool()


@pytest.fixture
def clean_db(db_pool):
    """각 테스트 시작 시 detections / posts / sources 테이블 TRUNCATE."""
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE detections, post_images, posts, sources RESTART IDENTITY CASCADE")
    yield db_pool
