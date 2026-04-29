from __future__ import annotations

import os

from detection.src.rate_limit.token_bucket import TokenBucket
from shared.interfaces.varco import ClassificationResult, VarcoInterface
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_ALLOWED_TYPES = frozenset({"매크로_판매", "핵_배포", "계정_거래", "리세마라", "기타"})
_logger = get_logger(__name__)


class LLMClassifier:
    def __init__(
        self,
        varco: VarcoInterface,
        token_bucket: TokenBucket,
        model_version: str | None = None,
    ) -> None:
        self._varco = varco
        self._bucket = token_bucket
        self._model_version = model_version or os.environ.get(
            "VARCO_LLM_MODEL_VERSION", "varco-llm-v1"
        )

    @property
    def model_version(self) -> str:
        return self._model_version

    def classify(self, text: str) -> ClassificationResult:
        self._bucket.acquire()
        result = self._varco.classify(text)

        if result.type not in _ALLOWED_TYPES:
            raise ValueError(f"invalid type: {result.type}")
        if not (0.0 <= result.confidence <= 1.0):
            raise ValueError(f"confidence out of range: {result.confidence}")

        return result
