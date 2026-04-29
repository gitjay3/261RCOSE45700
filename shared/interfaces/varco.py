from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ClassificationResult:
    is_illegal: bool
    type: str
    confidence: float
    reason: str


@runtime_checkable
class VarcoInterface(Protocol):
    def translate(self, text: str) -> str:
        """텍스트를 한국어로 번역.

        Raises:
            RateLimitError: VARCO API quota 초과 (호출자가 retry_after 후 1회 자동 재시도).
            TimeoutError: HTTP 호출 타임아웃 (RetryHandler retryable).
            ConnectionError / httpx.HTTPError: 네트워크/HTTP 오류 (RetryHandler retryable).
        """
        ...

    def classify(self, text: str) -> ClassificationResult:
        """텍스트의 불법 여부와 유형을 분류.

        Raises:
            RateLimitError: VARCO API quota 초과.
            TimeoutError / ConnectionError / httpx.HTTPError: RetryHandler retryable.
            ValueError: 응답 스키마 위반 (type/confidence 검증 실패) — non-retryable.
        """
        ...
