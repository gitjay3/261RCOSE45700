from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ClassificationResult:
    is_illegal: bool
    type: str
    confidence: float
    reason: str


# NOTE: Story 3-2 (VARCO Translation) deprecated by Sprint Change Proposal 2026-05-27.
# `translate()` 메서드 제거됨. classify() 경로는 Story 3-3에서 OpenAI 멀티모달로 재작성 예정.


@runtime_checkable
class VarcoInterface(Protocol):
    def classify(self, text: str) -> ClassificationResult:
        """텍스트의 불법 여부와 유형을 분류.

        Raises:
            RateLimitError: VARCO API quota 초과.
            TimeoutError / ConnectionError / httpx.HTTPError: RetryHandler retryable.
            ValueError: 응답 스키마 위반 (type/confidence 검증 실패) — non-retryable.
        """
        ...
