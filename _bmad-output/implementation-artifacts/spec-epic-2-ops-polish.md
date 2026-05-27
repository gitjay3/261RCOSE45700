---
title: 'Epic 2 ops polish (cleanup job + dcard_online fix + coalesce 명시)'
type: 'chore'
created: '2026-05-27'
status: 'done'
baseline_commit: '39acfa96f71711023da652f9e20b1e152c4f165c'
context:
  - '{project-root}/crawler/STATUS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/deferred-work.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 2 PR #46 직후 운영 갭 3건. (1) `UrlDedupChecker.cleanup_older_than()` 호출자 없음 → Redis ZSET `posts:seen_urls` 무한증식. (2) `SITES["dcard_online"]` `wait_for="css:article"` 타임아웃 → 1보드 회수율 0. (3) `crawl_pipeline` 잡 `coalesce` 미명시.

**Approach:** 한 PR 3건 polish. (1) cron 03:00 UTC 일일 청소 잡 등록. (2) `wait_for` 제거 + `delay_before_return_html=3.0` (Dcard React 해시 클래스 의존 회피). (3) `coalesce=True` 명시.

## Boundaries & Constraints

**Always:**
- 외부 컨트랙트(`posts:queue`, `CrawlEvent`, `crawl:trigger`) 무변경
- 142 기존 테스트 PASS 유지
- em-dash 금지, 주석은 WHY 비자명할 때만
- `SITES["dcard"]` (게임 보드) 무변경

**Ask First:**
- cron 시간 03:00 UTC 변경
- delay 3.0 외 다른 값

**Never:**
- Dcard JSON API endpoint 직결 (옵션 D) — deferred 등록만
- UndetectedAdapter — Story 2-8 흡수
- sync→async redis 전환 — deferred에 이미 있음
- `git push` / PR 생성 — 사용자 명시 후

## I/O & Edge-Case Matrix

| Scenario | Input | Behavior | Error |
|---|---|---|---|
| cleanup 정상 발화 | 03:00 UTC | `cleanup_older_than()` 1회, 건수 로그 | 다음 발화 대기 |
| cleanup misfire | 1h 내 복귀 | 따라잡기 1회 | grace 초과 시 `EVENT_JOB_MISSED` |
| dcard_online fetch | board URL | wait 없이 3초 hydration 대기 후 추출 | 빈 리스트 (기존) |
| crawl_pipeline missed 적체 | 다운 후 복귀 | `coalesce=True` 로 1회만 | `_on_job_missed` 로그 |

</frozen-after-approval>

## Code Map

- `crawler/src/scheduler/crawl_scheduler.py:373-387` -- `__init__` — `self._url_dedup` 분리 노출 필요
- `crawler/src/scheduler/crawl_scheduler.py:413-428` -- `setup_schedule()` — cleanup 잡 추가 + `coalesce=True`
- `crawler/src/preprocessor/url_dedup_checker.py:67-77` -- `cleanup_older_than()` (호출자 추가만)
- `crawler/src/sites/registry.py:313-327` -- `SITES["dcard_online"]` 수정
- `crawler/tests/unit/test_site_config.py` -- dcard_online 회귀 가드 갱신
- 신규 `crawler/tests/unit/test_scheduler_setup.py` -- 잡 등록 검증
- `_bmad-output/implementation-artifacts/deferred-work.md` -- 옵션 D + UndetectedAdapter 후속 등록

## Tasks & Acceptance

**Execution:**

- [ ] `crawler/src/scheduler/crawl_scheduler.py` -- `__init__` 에서 `self._url_dedup = UrlDedupChecker(dedup_client)` 분리, pipeline에 같은 인스턴스 주입 -- cleanup 잡과 파이프라인이 같은 ZSET 참조 보장
- [ ] `crawler/src/scheduler/crawl_scheduler.py` -- `async _cleanup_url_dedup_job(self)` 추가, `asyncio.to_thread(self._url_dedup.cleanup_older_than)` 호출 -- sync redis가 event loop 블락 방지
- [ ] `crawler/src/scheduler/crawl_scheduler.py` -- `setup_schedule()` 에 `add_job(CronTrigger(hour=3, minute=0), job_id="url_dedup_cleanup", misfire_grace_time=3600, max_instances=1, replace_existing=True, coalesce=True)` 추가 -- `from apscheduler.triggers.cron import CronTrigger` import
- [ ] `crawler/src/scheduler/crawl_scheduler.py` -- `crawl_pipeline` 잡에 `coalesce=True` + WHY 1줄 주석
- [ ] `crawler/src/sites/registry.py` -- `SITES["dcard_online"]` `wait_for` 라인 제거, `delay_before_return_html=3.0` 추가, `note` 1줄 갱신
- [ ] `crawler/tests/unit/test_scheduler_setup.py` (신규) -- Redis mock으로 `CrawlScheduler` 생성, `setup_schedule()` 호출 후 `_scheduler.get_jobs()` 가 2개 잡 반환 + 각 trigger/grace/coalesce 검증
- [ ] `crawler/tests/unit/test_site_config.py` -- dcard_online: `wait_for is None` + `delay_before_return_html == 3.0`. dcard (게임): `wait_for == "css:article"` 유지 회귀 가드
- [ ] `_bmad-output/implementation-artifacts/deferred-work.md` -- "## Deferred from: Epic 2 ops polish (2026-05-27)" 섹션 추가, 옵션 D (Dcard JSON API) + UndetectedAdapter 등록

**Acceptance Criteria:**

- Given `CrawlScheduler` 부팅, when `setup_schedule()`, then `get_jobs()` = `[crawl_pipeline, url_dedup_cleanup]`
- Given `url_dedup_cleanup` 발화, when handler, then `cleanup_older_than()` 1회 호출 (mock)
- Given `SITES["dcard_online"]`, then `wait_for is None` and `delay_before_return_html == 3.0`
- Given `SITES["dcard"]`, then `wait_for == "css:article"` (회귀 가드)
- Given `crawl_pipeline` 잡 kwargs, then `coalesce is True`
- Given `deferred-work.md`, then "Dcard JSON API endpoint" + "UndetectedAdapter" 두 항목 존재
- Given 전체 스위트, when `uv run pytest -q`, then 기존 142 + 신규 ~5 모두 PASS
- Given `uv run ruff check crawler/`, then 에러 0

## Spec Change Log

<!-- Empty until first review loopback. -->

## Verification

**Commands:**
- `uv run pytest -q` -- 142 + 신규 PASS, 외부 네트워크 0
- `uv run ruff check crawler/` -- 에러 0
- `uv run python -c "from crawler.src.scheduler.crawl_scheduler import CrawlScheduler; s=CrawlScheduler(); s.setup_schedule(); print([j.id for j in s._scheduler.get_jobs()])"` -- `['crawl_pipeline', 'url_dedup_cleanup']`

**Manual checks:**
- `uv run python scripts/smoke_each_site.py dcard_online` -- 외부 환경 수동. real >= 1 통과, board_ok + real==0 도 wait timeout 해소 판정
- `deferred-work.md` 상단 신규 섹션 + 2항목 시각 확인

## Suggested Review Order

**Cleanup 잡 등록 (entry — 가장 큰 디자인 변경)**

- 신규 일일 cleanup 잡 등록 — Redis ZSET 무한증식 차단의 핵심
  [`crawl_scheduler.py:435-446`](../../crawler/src/scheduler/crawl_scheduler.py#L435-L446)

- async handler — sync redis 호출을 thread로 오프로드해 이벤트 루프 보호
  [`crawl_scheduler.py:404-406`](../../crawler/src/scheduler/crawl_scheduler.py#L404-L406)

- 파이프라인과 cleanup 잡이 같은 ZSET 참조하도록 `_url_dedup` 인스턴스 외부 노출
  [`crawl_scheduler.py:380-386`](../../crawler/src/scheduler/crawl_scheduler.py#L380-L386)

- CronTrigger import (alphabetical 정렬)
  [`crawl_scheduler.py:13`](../../crawler/src/scheduler/crawl_scheduler.py#L13)

**Coalesce 명시 (운영 가시성)**

- 기존 crawl_pipeline 잡에 coalesce=True + WHY 주석 — 다운타임 복귀 시 missed run 적체 방지 의도 표현
  [`crawl_scheduler.py:427-432`](../../crawler/src/scheduler/crawl_scheduler.py#L427-L432)

**dcard_online 회수 복구**

- wait_for 셀렉터 제거 + 3초 delay fallback — Dcard React CSS module 해시(`PostList_entry_*`) 의존 회피
  [`registry.py:321-323`](../../crawler/src/sites/registry.py#L321-L323)

**테스트 (회귀 가드 + 신규 검증)**

- 신규 스케줄러 잡 등록·트리거·timezone·coalesce 검증 9건
  [`test_scheduler_setup.py:1`](../../crawler/tests/unit/test_scheduler_setup.py#L1)

- dcard_online fix 가드 + dcard 게임 보드 회귀 가드 2건
  [`test_site_config.py:198-209`](../../crawler/tests/unit/test_site_config.py#L198-L209)

**Out-of-scope 후속 등록**

- Dcard JSON API endpoint 직결 + UndetectedAdapter 옵션 슬롯 + APScheduler 잡 예외 핸들링 3건 deferred
  [`deferred-work.md:3-13`](./deferred-work.md#L3-L13)
