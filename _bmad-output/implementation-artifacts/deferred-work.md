# Deferred Work

## Deferred from: code review of 1-2-공유-인터페이스-계약-및-구조화-로깅-수립 (2026-04-27)

- **requirements.txt -e ../shared 상대경로** — CI 환경/컨테이너에서 경로가 깨질 수 있음. Story 1.5 CI 구성 시 절대경로 또는 workspace 기반 방식으로 교체.
- **pyproject.toml where=[".."] 비표준 설정** — setuptools가 모노레포 루트를 스캔하는 비표준 구성. 실제 배포 환경에서 검증 필요.
- **CrawlEvent.raw_text 크기 제한 없음** — 대형 게시글이 Redis에 수 MB 메시지로 전송될 수 있음. 부하 테스트 시 메시지 크기 상한 정의 필요.
- **VarcoInterface 메서드 예외 계약 없음** — translate/classify의 실패 시 예외 타입 미정의. Story 3.2 VarcoInterface 구현 시 예외 계약 문서화.
- **Redis key 상수 네임스페이스 없음** — `"posts:queue"` 등 bare string이 환경 간 충돌 가능. Story 1.3 환경 설정 시 prefix 전략 결정.
- **get_logger 멀티스레드 경쟁 조건** — `if not logger.handlers:` 체크가 thread-safe하지 않아 핸들러 중복 추가 가능. 실운영 전 검토.
- **ClassificationResult.confidence 범위 검증 없음** — `[0.0, 1.0]` 외 값 수용. Story 3.3 VARCO 연동 시 API 응답 검증 추가.
- **TrackerBaseException str() 시 correlation_id 누락** — `str(exc)` 호출 시 message만 출력. 로그 사용 가이드에 `logger.error(str(e), extra={"correlation_id": e.correlation_id})` 패턴 문서화.

## Deferred from: code review of 2-2-proxyprovider-추상화-및-기본-크롤러-구현 (2026-04-28)

- **ParseResult.image_urls 가변 리스트** — `@dataclass(frozen=True)`임에도 `image_urls: list[str]` 필드는 내용 변경 가능. 현 MVP에서는 실질적 위험 없으나, Story 2.3+ 모델 안정화 시 `tuple[str, ...]`로 전환 검토.
- **parse_list 외부 도메인 document_srl 교차 오염** — `urljoin` 처리 후 외부 도메인 링크에 `?document_srl=N`이 포함된 경우 tailstar 게시글로 오분류 가능. Story 2.5 통합 테스트 시 실제 사이트 목록 페이지로 검증.
- **test_proxy_provider.py async_playwright 동기 MagicMock 취약성** — `monkeypatch.setattr("...async_playwright", lambda: MagicMock())`이 async context manager 계약을 위반. 현 NFR15 swap 검증 목적에는 충분하나, StealthBrowser 리팩토링 시 mock 구조 재검토 필요.

## Deferred from: code review of 2-1-cloudflare-우회-가능성-검증 (2026-04-27)

- **하드코딩된 `Chrome/124` User-Agent 봇 탐지 지문화** — `crawler/src/browser/stealth_browser.py:15`. 이번 스파이크의 의도적 선택이나, 시간이 지남에 따라 구버전 UA로 봇 탐지율 증가. playwright 버전 핀 갱신 시 함께 업데이트 필요. Story 2.2+ 추적.
- **`Stealth().use_async(async_playwright())` 내부 CM 진입/탈출 보장 여부** — `crawler/src/browser/stealth_browser.py:57`. playwright-stealth 2.x 라이브러리가 `async_playwright()` CM을 올바르게 진입/탈출하는지 소스 검증 필요. 통합 테스트에서 Chromium 프로세스 누수 모니터링.
- **`response=None` 시 불충분한 오류 메시지** — `crawler/src/browser/stealth_browser.py:91`. `"unexpected HTTP status None"` 메시지로는 "서버 응답 없음" 원인 파악 불가. Story 2.2 리파인 시 개선.
- **`crawler/__init__.py` 추가로 잠재적 패키지 임포트 경로 충돌** — `crawler/__init__.py`. 모노레포 구조에서 의도된 배치이나, 배포 환경에서 동명 PyPI 패키지와 충돌 가능성 검토 필요.
