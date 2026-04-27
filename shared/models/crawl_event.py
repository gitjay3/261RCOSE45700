from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

_CRAWL_EVENT_FIELDS = frozenset({
    "post_id", "source_id", "site_name", "raw_text",
    "language", "detected_at", "correlation_id", "image_urls",
})


@dataclass
class CrawlEvent:
    post_id: str
    source_id: str
    site_name: str
    raw_text: str
    language: str
    detected_at: str
    correlation_id: str
    image_urls: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> CrawlEvent:
        payload = json.loads(data)
        unknown = set(payload) - _CRAWL_EVENT_FIELDS
        if unknown:
            raise ValueError(f"CrawlEvent: unknown fields in payload: {unknown}")
        missing = _CRAWL_EVENT_FIELDS - {"image_urls"} - set(payload)
        if missing:
            raise ValueError(f"CrawlEvent: missing required fields: {missing}")
        if not isinstance(payload.get("image_urls", []), list):
            raise ValueError("CrawlEvent: 'image_urls' must be a list")
        return cls(**{k: v for k, v in payload.items() if k in _CRAWL_EVENT_FIELDS})
