# Story 3.0: SPIKE — OpenAI 멀티모달 LLM PoC

Status: done

> **Smoke-level closed (2026-05-27).** Sprint Change Proposal 2026-05-27의 "1일 타임박스 SPIKE" 목적은 (a) OpenAI 키·네트워크·모델 가용성 (b) `response_format=json_schema` 동작 (c) 게시글당 단가 한 자리 수치 — 이 3개만 확인하면 충분하다는 운영자 결정. 무거운 검증(Tier별 라벨셋 ≥7건, 이미지 ≥10건, 외국어 ≥15건, PII 1차 검토)은 본 SPIKE에서 빼고 Story 3-5(정확도 측정) / Story 3-6(이미지 PII 토글)에서 다룬다.

## 검증 결과 (이미 산출됨)

| 항목 | 결과 | 산출물 |
|---|---|---|
| OpenAI 키 + 네트워크 + `gpt-4o` 호출 | OK | `detection/scripts/smoke_openai.py` |
| `response_format=json_schema` strict mode 동작 | OK (`{type, tier, confidence, reason_ko, translated_text_ko}` 강제) | smoke_openai.py 호출 결과 |
| 30 sample 합성 라벨셋 통과 (illegal 15 / clean 15) | 30/30 호출 성공 | `detection/scripts/spike_llm.py` |
| 게시글당 평균 비용 (텍스트 only) | **$0.0019 USD** (PRD ≤ $0.005 통과) | `docs/llm-spike-2026-05-27.md` §2 |
| p95 latency | **3.69s** (목표 ≤ 30분 배치에 충분한 여유) | `docs/llm-spike-2026-05-27.md` §2 |
| illegal Recall (T1/T2/T3 탐지) | 100% (15/15) | `docs/llm-spike-2026-05-27.md` §3 |
| clean Specificity (T4 유지) | 93.3% (14/15) | `docs/llm-spike-2026-05-27.md` §3 |
| Tier confusion matrix | T1/T2/T3 = 100%, T4 = 77.8% | `docs/llm-spike-2026-05-27.md` §3 |

## Story 3-3 본 구현 입력값 (확정)

| 항목 | 권장값 | 근거 |
|---|---|---|
| 모델 | `gpt-4o` | smoke + 30 sample 검증값 |
| `response_format` | `json_schema` strict mode | smoke 검증 |
| Schema 필드 | `type / confidence / reason_ko / translated_text_ko / image_observed` | `spike_llm.py::CLASSIFICATION_SCHEMA` |
| Tier 매핑 | 코드(`tier_router.py`) — `spike_llm.py::NEW_TYPE_TO_TIER` 이식 | SPIKE 검증 |
| 일일 비용 cap 초기값 | **$5** (≈ 2,628건/일 처리 여유, baseline $0.0019/post 기준) | SPIKE §2 |
| Worker 동시성 초기값 | 1 | 보수적, rate limit/예산 운영 데이터로 조정 |
| 타임아웃 | 30s | smoke + SPIKE 검증 |
| 이미지 처리 방침 | `LLM_SEND_IMAGES=false` 시작 → Story 3-6 진입 전 법무 검토 후 true | 본 SPIKE에서 이미지 검증 미수행 |
| 텍스트/이미지 호출 분리 | `LLM_SPLIT_TEXT_IMAGE=false` (단일 호출) | 비용·정확도 측정은 Story 3-5에서 |

## 후속 스토리로 이월된 항목

- **이미지 분석 검증** — Story 3-3 본 구현 시 실 크롤 이미지 1~2건으로 dev 자가 spot-check, 본격 검증은 Story 3-5 라벨셋 v2(이미지 ≥50건 포함).
- **외국어 번역 품질** — 실 크롤 zh-CN/zh-TW 게시글이 누적되면 Story 3-5에서 spot-check.
- **이미지 PII 컴플라이언스 정식 검토** — Story 3-6 진입 전 PM/법무 트랙. 그 전까지는 `LLM_SEND_IMAGES=false`.
- **Tier별 정확도 정식 측정** — Story 3-5 라벨셋 ≥300건 + Tier별 ≥75건.

## 산출물 위치

- `detection/scripts/smoke_openai.py` — 키/네트워크/json_schema smoke
- `detection/scripts/spike_llm.py` — 30 sample 분류·비용·latency 측정
- `docs/llm-spike-2026-05-27.md` — 결과 보고서
- `docs/llm-spike-raw-2026-05-27.jsonl` — 30 sample 원자료
- `tests/fixtures/labels/manual_label_set_v1.csv` — 200건 baseline 라벨셋

## References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-05-27.md] — Epic 3 PIVOT 전체 배경
- [Source: _bmad-output/planning-artifacts/epics.md#SPIKE 3.0] — L554-571 원 AC (본 스토리는 smoke 수준으로 축약 closed)
- [Source: docs/llm-spike-2026-05-27.md] — 측정 결과 본문

## Dev Agent Record

### Completion Notes List

- 2026-05-27: smoke_openai.py + spike_llm.py 30 sample 결과로 Story 3-3 입력값 확정. 운영자 결정으로 무거운 보조 AC(라벨셋 ≥7/Tier, 이미지 ≥10, 외국어 ≥15, PII 1차 검토)는 Story 3-5/3-6으로 이월. 본 스토리는 closed.

### File List

- `detection/scripts/smoke_openai.py` (신규)
- `detection/scripts/spike_llm.py` (신규)
- `docs/llm-spike-2026-05-27.md` (신규)
- `docs/llm-spike-raw-2026-05-27.jsonl` (신규)
