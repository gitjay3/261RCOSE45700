# shared

crawler와 detection이 공통으로 사용하는 Python 모듈 패키지. `pip install -e ../shared`로 두 서브시스템 venv에 editable 링크로 설치된다.

---

## 설치

각 서브시스템 `requirements.txt`에 이미 포함돼 있어 별도 설치 불필요.

```bash
# crawler 또는 detection venv에서 수동 설치할 경우
pip install -e path/to/shared
```

---

## 모듈 목록

| 모듈 | 설명 |
|---|---|
| `shared.models.crawl_event` | Redis MQ 메시지 스키마 (`CrawlEvent` dataclass) — crawler → detection 계약 |
| `shared.interfaces.llm` | `LLMInterface` Protocol — `LLMClient`와 `LLMMock`의 공통 타입 계약 |
| `shared.config.redis_config` | Redis DB 번호 상수 (`REDIS_MQ_DB=0`, `REDIS_DEDUP_DB=1`, `REDIS_RATELIMIT_DB=2`, `REDIS_CACHE_DB=3`) + 키 상수 |
| `shared.correlation_id` | 요청 추적용 UUID 생성·전파 (`get_correlation_id`, `set_correlation_id`) |
| `shared.structured_logger` | JSON 구조화 로그 (correlation_id 자동 포함) |
| `shared.exceptions.base_exception` | `TrackerBaseException` 공통 예외 계층 |

---

## 디렉터리 구조

```
shared/
├── pyproject.toml          # 패키지 메타데이터 (name: tracker-shared)
├── correlation_id.py
├── structured_logger.py
├── config/
│   └── redis_config.py     # DB 번호 + 키 이름 상수
├── exceptions/
│   └── base_exception.py
├── interfaces/
│   └── llm.py              # LLMInterface Protocol
└── models/
    └── crawl_event.py      # CrawlEvent — posts:queue Redis MQ 메시지 계약
```

---

## 계약 변경 주의

`CrawlEvent`와 `LLMInterface`는 crawler와 detection 양쪽이 동시에 참조하므로, 필드 추가·제거·타입 변경 시 두 서브시스템을 함께 업데이트해야 한다.
