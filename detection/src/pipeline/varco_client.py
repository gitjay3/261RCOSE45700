from __future__ import annotations

import os

import httpx

from detection.src.mocks.varco_mock import RateLimitError
from shared.interfaces.varco import ClassificationResult


class VarcoHttpClient:
    """VarcoInterface 구현 — 실제 VARCO API 호출. 엔드포인트는 환경변수로 주입."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        base_url = os.environ.get("VARCO_API_BASE_URL", "https://varco.placeholder/v1")
        api_key = os.environ.get("VARCO_API_KEY", "")
        timeout = float(os.environ.get("VARCO_TRANSLATE_TIMEOUT_SEC", "10"))
        self._client = client or httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=timeout,
        )

    def translate(self, text: str) -> str:
        response = self._client.post("/translate", json={"text": text, "target": "ko"})
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "30"))
            raise RateLimitError(retry_after)
        response.raise_for_status()
        return response.json()["translated_text"]

    def classify(self, text: str) -> ClassificationResult:
        timeout = float(os.environ.get("VARCO_CLASSIFY_TIMEOUT_SEC", "10"))
        response = self._client.post("/classify", json={"text": text}, timeout=timeout)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "30"))
            raise RateLimitError(retry_after)
        response.raise_for_status()
        data = response.json()
        return ClassificationResult(
            is_illegal=bool(data["is_illegal"]),
            type=str(data["type"]),
            confidence=float(data["confidence"]),
            reason=str(data["reason"]),
        )
