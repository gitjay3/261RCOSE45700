from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from detection.src.mocks.varco_mock import VarcoMock
from detection.src.pipeline.llm_classifier import LLMClassifier
from shared.interfaces.varco import ClassificationResult


def test_classifies_clean_text() -> None:
    bucket = MagicMock()
    varco = VarcoMock(mode="clean")
    classifier = LLMClassifier(varco, bucket)

    result = classifier.classify("정상적인 게시글")

    assert result.is_illegal is False
    assert result.type == "기타"
    assert result.confidence == 0.92
    bucket.acquire.assert_called_once()


def test_classifies_illegal_text() -> None:
    bucket = MagicMock()
    varco = VarcoMock(mode="illegal")
    classifier = LLMClassifier(varco, bucket)

    result = classifier.classify("매크로 판매합니다")

    assert result.is_illegal is True
    assert result.type == "매크로_판매"
    assert result.confidence == 0.95


def test_invalid_type_raises_value_error() -> None:
    bucket = MagicMock()
    varco = MagicMock()
    varco.classify.return_value = ClassificationResult(
        is_illegal=True, type="invalid_type", confidence=0.9, reason="...",
    )
    classifier = LLMClassifier(varco, bucket)

    with pytest.raises(ValueError, match="invalid type: invalid_type"):
        classifier.classify("text")


def test_confidence_above_one_raises_value_error() -> None:
    bucket = MagicMock()
    varco = MagicMock()
    varco.classify.return_value = ClassificationResult(
        is_illegal=True, type="기타", confidence=1.5, reason="...",
    )
    classifier = LLMClassifier(varco, bucket)

    with pytest.raises(ValueError, match="confidence out of range: 1.5"):
        classifier.classify("text")


def test_confidence_below_zero_raises_value_error() -> None:
    bucket = MagicMock()
    varco = MagicMock()
    varco.classify.return_value = ClassificationResult(
        is_illegal=False, type="기타", confidence=-0.1, reason="...",
    )
    classifier = LLMClassifier(varco, bucket)

    with pytest.raises(ValueError, match="confidence out of range: -0.1"):
        classifier.classify("text")
