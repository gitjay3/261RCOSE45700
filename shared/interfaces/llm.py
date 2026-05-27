"""LLM Protocol — Story 3-3 (2026-05-27 PIVOT).

OpenAI 멀티모달 LLM 단일 호출 계약.
구 분류 계약은 본 모듈로 이전됨.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResponse:
    """OpenAI 멀티모달 단일 호출 응답.

    SPIKE 3.0의 `CLASSIFICATION_SCHEMA` 5필드 + token usage + 비용.
    Story 3-4에서 RDS `detections` 테이블에 그대로 매핑.
    """

    type: str
    confidence: float
    reason_ko: str
    translated_text_ko: str | None
    image_observed: bool
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


# RateLimitError는 OpenAI 429 / rate-limited mock을 호출자에게 통보하는 본 모듈 공용 예외.
class RateLimitError(Exception):
    """LLM API rate limit 또는 quota 초과. 호출자가 Retry-After sleep 후 자체 재시도."""

    def __init__(self, retry_after: int = 30) -> None:
        self.retry_after = retry_after
        super().__init__(f"LLM rate limit exceeded. Retry after {retry_after}s")


@runtime_checkable
class LLMInterface(Protocol):
    """텍스트(+선택적 이미지) 분류 인터페이스.

    Raises:
        RateLimitError: API quota 초과. RetryHandler가 catch하지 않음(호출자 책임).
        TimeoutError / ConnectionError / httpx.HTTPError / openai.APITimeoutError /
            openai.APIConnectionError: RetryHandler retryable.
        ValueError: 응답 스키마 위반(type enum / confidence 범위 등) — non-retryable.
    """

    def classify(self, text: str, images: list[str] | None = None) -> LLMResponse: ...
