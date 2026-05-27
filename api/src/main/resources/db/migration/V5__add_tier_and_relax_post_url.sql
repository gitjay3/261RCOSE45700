-- Story 3-4 (Sprint Change Proposal 2026-05-27 PIVOT)
-- Detection이 RDS에 결과를 저장할 수 있도록 스키마 확장.
--
-- 변경 요약:
--   1) sources(site_name) UNIQUE — detection이 ON CONFLICT로 UPSERT 하기 위함
--   2) posts.post_url NOT NULL → NULLABLE — CrawlEvent에 post_url이 없는 경우 허용
--      (crawler가 향후 채우면 그때 NOT NULL 복원 가능)
--   3) detections: tier / image_observed / token_usage_json / cost_usd 컬럼 추가
--      - tier: T1=핵_치트/사설서버/불법프로그램_배포, T2=계정_거래/매크로_판매,
--              T3=리세마라/현금화/광고_도배, T4=기타
--      - threshold는 대시보드 디스플레이 필터로만 작동 (전수 저장 정책 — 부록 A-2)
--   4) idx_detections_filter 인덱스 재생성 — tier 컬럼 우선
--   5) translated_text (V4 추가됨) 그대로 재사용 — LLMResponse.translated_text_ko 값을 매핑

-- 1) sources.site_name UNIQUE
ALTER TABLE sources
    ADD CONSTRAINT sources_site_name_unique UNIQUE (site_name);

-- 2) sources.base_url NULLABLE — CrawlEvent에 base_url 정보가 없음, detection은 sources를 lazy create만 함
ALTER TABLE sources
    ALTER COLUMN base_url DROP NOT NULL;

-- 3) posts.post_url NULLABLE
ALTER TABLE posts
    ALTER COLUMN post_url DROP NOT NULL;

-- 4) detections 컬럼 추가
ALTER TABLE detections
    ADD COLUMN tier             VARCHAR(2) NOT NULL DEFAULT 'T4'
        CHECK (tier IN ('T1', 'T2', 'T3', 'T4'));
ALTER TABLE detections
    ADD COLUMN image_observed   BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE detections
    ADD COLUMN token_usage_json JSONB;
ALTER TABLE detections
    ADD COLUMN cost_usd         NUMERIC(8, 5);

-- 5) idx_detections_filter 재생성 — tier를 두 번째 정렬 키로
DROP INDEX IF EXISTS idx_detections_filter;
CREATE INDEX idx_detections_filter
    ON detections (detected_at DESC, tier, type, confidence DESC);
