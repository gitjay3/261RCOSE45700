# crawler_test

NC 게임(리니지 / 아이온 / BNS / TL 등) 사설서버·매크로·핵 탐지를 위한 한·중·대만권 게시판 크롤링.

> **전체 현황·아키텍처·운영 다이얼은 [STATUS.md](./STATUS.md) 참조.** 이 문서는 빠른 시작 가이드입니다.

---

## 빠른 시작

```bash
cd crawler_test

# 1) 의존성 설치 (.venv + uv.lock 자동)
uv sync

# 2) Playwright Chromium (최초 1회만)
uv run playwright install chromium

# 3) 단위/통합 테스트 (mock, 인터넷 불필요)
uv run pytest -q                              # 142 passed 예상

# 4) ruff 린트
uv run ruff check crawler/ shared/ scripts/

# 5) 실 사이트 smoke (tieba/nga 자동 제외)
uv run python scripts/smoke_each_site.py
uv run python scripts/smoke_each_site.py bahamut_tl    # 특정 사이트만
```

---

## 디렉터리 구조

```
crawler_test/
├── pyproject.toml          # uv + pytest + ruff
├── uv.lock
├── STATUS.md               # ⭐ 전체 현황 / 아키텍처 / 사이트별 진단
├── README.md               # 이 문서 (빠른 시작)
├── crawler/
│   ├── src/                # 본체
│   │   ├── crawl4ai_crawler.py
│   │   ├── storage.py · s3_uploader.py
│   │   ├── preprocessor/   # content_validator, dedup_checker,
│   │   │                   # url_dedup_checker, language_detector, serializer
│   │   ├── queue/          # redis_publisher
│   │   ├── scheduler/      # crawl_scheduler (CrawlPipeline + APScheduler) + trigger_listener
│   │   └── sites/          # registry — SiteConfig + SITES dict
│   └── tests/              # unit + integration (142건)
├── shared/                 # crawl_event, redis_config, logger 등 공용
└── scripts/
    └── smoke_each_site.py  # 실 사이트 검증 (수동 실행)
```

---

## 운영 (Redis 필요)

```bash
# 가장 단순한 형태 — 기본 60분 주기, 보드당 10건
REDIS_URL=redis://localhost:6379 \
uv run python -m crawler.src.scheduler.crawl_scheduler

# 30분 주기, S3 업로드, 보드당 5건
REDIS_URL=redis://localhost:6379 \
CRAWL_INTERVAL_MINUTES=30 \
MAX_POSTS_PER_BOARD=5 \
ENABLE_S3_UPLOAD=true \
S3_BUCKET_NAME=my-bucket \
AWS_REGION=ap-northeast-2 \
uv run python -m crawler.src.scheduler.crawl_scheduler
```

전체 환경변수 목록은 [STATUS.md §5](./STATUS.md#5-운영-다이얼-환경변수) 참조.

---

## 새 사이트 추가하기

`crawler/src/sites/registry.py` 의 `SITES` dict 에 한 줄 추가하면 끝.

```python
"my_new_board": SiteConfig(
    name="신규 보드",
    description="...",
    board_urls=["https://example.com/board/page1"],
    post_url_pattern=r"https://example\.com/post/\d+",
    css_selector=".article-body",
    # 필요 시 cookies / wait_for / headers / js_code / proxy / title_keywords 등
    enabled=True,
),
```

Validator는 prefix dispatch — `my_new_*` 같은 family 추가 시 `content_validator.py` 의 `PREFIX_VALIDATORS` 에 한 줄 추가하거나, `SITE_VALIDATORS` 에 정확 매칭으로 등록.

---

## 외부 서비스 의존성

| 서비스 | 용도 | 단위 테스트에선 |
|---|---|---|
| Redis | posts:queue, dedup, URL seen, crawl:trigger | MagicMock |
| boto3 / S3 | 옵션 (ENABLE_S3_UPLOAD=true 시) | unittest.mock.patch |
| crawl4ai (Playwright) | 브라우저 자동화 | patch("...AsyncWebCrawler") |

→ **`uv run pytest` 는 외부 서비스 없이 100% mock 으로 동작.**
→ 실 사이트 smoke 만 인터넷 + Chromium 필요.

---

## 다음 단계

- [ ] dcard_online `wait_for` 셀렉터 수정
- [ ] ptt_mobile_game / dcard 페이지네이션
- [ ] 검색엔진형 추상화 (`SearchEngineConfig`) + github 첫 도전
- [ ] enrichment 서비스 신설 (DeepSeek + OpenAI VLM)
- [ ] 중국 IP 프록시 인프라 (nga/tieba/baidu/sogou)

자세한 로드맵은 [STATUS.md §10](./STATUS.md#10-roadmap-우선순위) 참조.
