"""SPIKE 3.0 — OpenAI 멀티모달 LLM PoC (Sprint Change Proposal 2026-05-27).

목표: 1일 안에 OpenAI 멀티모달 LLM이 게임 도메인 라벨셋에서 동작함을 검증하고,
Story 3-3 본 구현에 사용할 권장 모델·프롬프트·response schema·일일 비용 cap 초기값을
사실 기반으로 결정한다.

검증 항목 (Sprint Change Proposal §부록 + Epic 3 SPIKE 3.0 AC):
- 멀티모달 단일 호출 동작 (텍스트 — 본 SPIKE는 이미지 없음)
- response_format=json_schema 구조화 출력 동작
- Tier 매핑 정확도 (T1/T2/T3/T4)
- 게시글당 평균 비용 (USD)
- p95 latency
- 다국어 번역 — 본 SPIKE는 한국어 라벨셋만이라 한계로 기록

Usage:
    python detection/scripts/spike_llm.py [--sample-size N] [--seed S]

Output:
    docs/llm-spike-2026-05-27.md (마크다운 보고서)
    docs/llm-spike-raw-2026-05-27.jsonl (원자료 — 디버깅용)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ============================================================
# 환경 로딩
# ============================================================

try:
    from dotenv import load_dotenv
    from openai import OpenAI, OpenAIError
except ImportError as e:
    sys.exit(f"[FAIL] 의존성 미설치: {e}. `pip install -r detection/requirements.txt` 실행.")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / "infra" / ".env"
LABELSET_PATH = PROJECT_ROOT / "tests" / "fixtures" / "labels" / "manual_label_set_v1.csv"
DOCS_DIR = PROJECT_ROOT / "docs"
REPORT_PATH = DOCS_DIR / "llm-spike-2026-05-27.md"
RAW_PATH = DOCS_DIR / "llm-spike-raw-2026-05-27.jsonl"

if not ENV_PATH.exists():
    sys.exit(f"[FAIL] {ENV_PATH} 없음.")
load_dotenv(ENV_PATH)

API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not API_KEY or API_KEY.startswith("sk-REPLACE"):
    sys.exit("[FAIL] OPENAI_API_KEY placeholder. infra/.env 갱신 필요.")

MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
TIMEOUT_SEC = float(os.environ.get("LLM_TIMEOUT_SEC", "30"))

# ============================================================
# Tier 매핑 (Sprint Change Proposal §1 + PRD FR12)
# ============================================================
# 신규 type enum → Tier
NEW_TYPE_TO_TIER: dict[str, str] = {
    "핵_치트": "T1",
    "사설서버": "T1",
    "불법프로그램_배포": "T1",
    "계정_거래": "T2",
    "매크로_판매": "T2",
    "리세마라": "T3",
    "현금화": "T3",
    "광고_도배": "T3",
    "기타": "T4",
}

# 구 라벨셋(manual_label_set_v1.csv) type → 신규 type (정답 비교용)
OLD_TYPE_TO_NEW: dict[str, str] = {
    "핵_배포": "불법프로그램_배포",  # 또는 핵_치트, 둘 다 T1이므로 Tier 매칭은 동일
    "매크로_판매": "매크로_판매",
    "리세마라": "리세마라",
    "계정_거래": "계정_거래",
    "기타": "기타",
    "": "기타",  # clean 행 (label=clean, type 빈 값) → 기타 / T4 처리
}

# ============================================================
# OpenAI 단가 (2026-05 기준, USD per 1M tokens)
# https://openai.com/api/pricing/
# 정확값은 시점에 따라 변동, SPIKE에서는 추정용
# ============================================================
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.400, "output": 1.600},
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """단가 미등록 모델은 gpt-4o 가격으로 fallback."""
    rate = PRICING.get(model) or PRICING.get(model.split("-")[0] + "-" + model.split("-")[1], None) or PRICING["gpt-4o"]
    return (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000


# ============================================================
# 프롬프트 + Schema
# ============================================================

SYSTEM_PROMPT = (
    "당신은 NC AI 게임 보안 분석가입니다. 주어진 커뮤니티 게시글의 불법성을 판단하세요.\n"
    "다음 type enum 중 하나로 분류:\n"
    "- 핵_치트: 게임 핵·치트 프로그램 자체 (탐지 회피, 무적, 자동 조준 등)\n"
    "- 사설서버: 비공식 게임 서버 운영·홍보\n"
    "- 불법프로그램_배포: 핵 외 매크로·봇·자동화 도구 배포\n"
    "- 계정_거래: 게임 계정 현금 거래\n"
    "- 매크로_판매: 매크로·자동사냥 프로그램 판매\n"
    "- 리세마라: 초기화·리세마라 계정 판매·대행\n"
    "- 현금화: 게임 머니/아이템 현금화·환전\n"
    "- 광고_도배: 무관 광고·스팸\n"
    "- 기타: 위 카테고리에 해당 안 함 (합법 게시글 포함)\n\n"
    "한국어 외 본문은 translated_text_ko에 자연스러운 한국어 번역을 포함. 한국어 원문은 null.\n"
    "reason_ko는 항상 한국어로 작성. 판단 근거를 1-2문장."
)


CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": list(NEW_TYPE_TO_TIER.keys()),
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason_ko": {"type": "string"},
        "translated_text_ko": {"type": ["string", "null"]},
        "image_observed": {"type": "boolean"},
    },
    "required": ["type", "confidence", "reason_ko", "translated_text_ko", "image_observed"],
    "additionalProperties": False,
}


# ============================================================
# Sampling
# ============================================================

def load_labelset(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def stratified_sample(rows: list[dict[str, str]], n: int, seed: int) -> list[dict[str, str]]:
    """illegal/clean을 균등하게, illegal 내 type도 균등하게 추출."""
    rng = random.Random(seed)
    illegal = [r for r in rows if r["label"] == "illegal"]
    clean = [r for r in rows if r["label"] == "clean"]

    # illegal n//2, clean n//2 (홀수 시 clean에 +1)
    n_illegal = n // 2
    n_clean = n - n_illegal

    # illegal은 type별 균등 시도
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in illegal:
        by_type[r["type"]].append(r)
    types = list(by_type.keys())
    per_type = max(1, n_illegal // len(types))

    sampled_illegal: list[dict] = []
    for t in types:
        rng.shuffle(by_type[t])
        sampled_illegal.extend(by_type[t][:per_type])
    # 부족분은 임의 보충
    if len(sampled_illegal) < n_illegal:
        remaining = [r for r in illegal if r not in sampled_illegal]
        rng.shuffle(remaining)
        sampled_illegal.extend(remaining[: n_illegal - len(sampled_illegal)])
    sampled_illegal = sampled_illegal[:n_illegal]

    rng.shuffle(clean)
    sampled_clean = clean[:n_clean]

    result = sampled_illegal + sampled_clean
    rng.shuffle(result)
    return result


# ============================================================
# 분류 호출
# ============================================================

def classify(client: OpenAI, text: str) -> tuple[dict[str, Any], int, int, float, str | None]:
    """단일 게시글 분류. 반환: (parsed_response, input_tokens, output_tokens, latency_sec, error_msg)"""
    t0 = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"게시글:\n{text}"},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "tracker_classification",
                    "strict": True,
                    "schema": CLASSIFICATION_SCHEMA,
                },
            },
        )
    except OpenAIError as e:
        return {}, 0, 0, time.monotonic() - t0, f"{type(e).__name__}: {e}"
    except Exception as e:
        return {}, 0, 0, time.monotonic() - t0, f"{type(e).__name__}: {e}"

    latency = time.monotonic() - t0
    content = resp.choices[0].message.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        return {}, resp.usage.prompt_tokens, resp.usage.completion_tokens, latency, f"JSONDecodeError: {e} | raw={content[:200]}"

    return parsed, resp.usage.prompt_tokens, resp.usage.completion_tokens, latency, None


# ============================================================
# 메인
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="SPIKE 3.0 — OpenAI 멀티모달 PoC")
    parser.add_argument("--sample-size", type=int, default=30, help="추출 건수 (기본 30)")
    parser.add_argument("--seed", type=int, default=42, help="random seed (기본 42)")
    args = parser.parse_args()

    print(f"[INFO] SPIKE 3.0 시작")
    print(f"[INFO] model={MODEL}, sample={args.sample_size}, seed={args.seed}")
    print(f"[INFO] labelset: {LABELSET_PATH}")

    rows = load_labelset(LABELSET_PATH)
    print(f"[INFO] 전체 라벨셋: {len(rows)}건")
    samples = stratified_sample(rows, args.sample_size, args.seed)
    print(f"[INFO] 추출: {len(samples)}건 (illegal {sum(1 for r in samples if r['label']=='illegal')} / clean {sum(1 for r in samples if r['label']=='clean')})")

    client = OpenAI(api_key=API_KEY, timeout=TIMEOUT_SEC)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # 정답 — 구 type → 신규 type → Tier
    def ground_truth_tier(row: dict[str, str]) -> str:
        if row["label"] == "clean":
            return "T4"  # clean은 사실상 "탐지 안 됨" — 기타/T4로 비교
        new_type = OLD_TYPE_TO_NEW.get(row["type"], "기타")
        return NEW_TYPE_TO_TIER[new_type]

    results: list[dict[str, Any]] = []
    raw_lines: list[str] = []

    for i, row in enumerate(samples, 1):
        gt_tier = ground_truth_tier(row)
        gt_label = row["label"]

        print(f"  [{i:2d}/{len(samples)}] {row['post_id']} (gt={gt_tier}, {gt_label})...", end="", flush=True)

        parsed, in_tok, out_tok, latency, err = classify(client, row["text"])
        cost = estimate_cost_usd(MODEL, in_tok, out_tok)

        if err:
            print(f" FAIL ({err[:80]})")
            results.append({
                "post_id": row["post_id"],
                "text": row["text"],
                "gt_label": gt_label,
                "gt_old_type": row["type"],
                "gt_tier": gt_tier,
                "pred_type": None,
                "pred_tier": None,
                "confidence": None,
                "reason_ko": None,
                "translated_text_ko": None,
                "image_observed": None,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": cost,
                "latency_sec": latency,
                "error": err,
            })
        else:
            pred_type = parsed.get("type", "기타")
            pred_tier = NEW_TYPE_TO_TIER.get(pred_type, "T4")
            print(f" OK pred={pred_type}/{pred_tier} conf={parsed.get('confidence', 0):.2f} {latency:.2f}s ${cost:.4f}")
            results.append({
                "post_id": row["post_id"],
                "text": row["text"],
                "gt_label": gt_label,
                "gt_old_type": row["type"],
                "gt_tier": gt_tier,
                "pred_type": pred_type,
                "pred_tier": pred_tier,
                "confidence": parsed.get("confidence"),
                "reason_ko": parsed.get("reason_ko"),
                "translated_text_ko": parsed.get("translated_text_ko"),
                "image_observed": parsed.get("image_observed"),
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": cost,
                "latency_sec": latency,
                "error": None,
            })

        raw_lines.append(json.dumps(results[-1], ensure_ascii=False))

    # ============================================================
    # 집계
    # ============================================================
    success = [r for r in results if r["error"] is None]
    failed = [r for r in results if r["error"] is not None]

    total_cost = sum(r["cost_usd"] for r in results)
    avg_cost = total_cost / max(1, len(results))
    latencies = sorted(r["latency_sec"] for r in success)
    p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0
    avg_latency = statistics.mean(latencies) if latencies else 0

    # Tier confusion matrix
    tier_cm: dict[tuple[str, str], int] = defaultdict(int)
    for r in success:
        tier_cm[(r["gt_tier"], r["pred_tier"])] += 1

    # 이진 정확도 (illegal/clean — clean → T4로 매핑됨, illegal → T1/T2/T3 중 하나)
    illegal_detected_correctly = sum(1 for r in success if r["gt_label"] == "illegal" and r["pred_tier"] in {"T1", "T2", "T3"})
    illegal_total = sum(1 for r in success if r["gt_label"] == "illegal")
    clean_kept_clean = sum(1 for r in success if r["gt_label"] == "clean" and r["pred_tier"] == "T4")
    clean_total = sum(1 for r in success if r["gt_label"] == "clean")

    recall_illegal = illegal_detected_correctly / illegal_total if illegal_total else 0
    specificity_clean = clean_kept_clean / clean_total if clean_total else 0

    # Per-Tier metrics (gt tier 기준)
    tier_total: dict[str, int] = Counter(r["gt_tier"] for r in success)
    tier_correct: dict[str, int] = Counter(r["gt_tier"] for r in success if r["gt_tier"] == r["pred_tier"])

    # ============================================================
    # 보고서 작성
    # ============================================================
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md = f"""# SPIKE 3.0 — OpenAI 멀티모달 LLM PoC 결과

**일자**: {now}
**Sprint Change Proposal**: `sprint-change-proposal-2026-05-27.md`
**Story**: Epic 3 SPIKE 3.0 (1일 타임박스)

## 1. 실행 환경

| 항목 | 값 |
|------|---|
| 모델 | `{MODEL}` |
| 라벨셋 | `{LABELSET_PATH.relative_to(PROJECT_ROOT)}` ({len(rows)}건 중 {len(samples)} 추출) |
| Seed | {args.seed} |
| Sample 구성 | illegal {sum(1 for r in samples if r['label']=='illegal')} / clean {sum(1 for r in samples if r['label']=='clean')} |
| 호출 성공 | {len(success)} / {len(results)} |
| 호출 실패 | {len(failed)} |
| 타임아웃 | {TIMEOUT_SEC:.0f}s |

## 2. 비용·성능 지표

| 지표 | 값 |
|------|---|
| **총 비용** | ${total_cost:.4f} USD |
| **게시글당 평균 비용** | ${avg_cost:.4f} USD |
| 입력 토큰 합 | {sum(r['input_tokens'] for r in results):,} |
| 출력 토큰 합 | {sum(r['output_tokens'] for r in results):,} |
| 평균 latency | {avg_latency:.2f}s |
| **p95 latency** | {p95_latency:.2f}s |

**목표 대비** (PRD Success Criteria):
- 게시글당 비용 ≤ $0.005 → {'✅ 통과' if avg_cost <= 0.005 else f'⚠️ 초과 ({avg_cost/0.005:.1f}x)'}
- 일일 cap $5 기준 처리 가능량 ≈ **{int(5 / max(0.0001, avg_cost)):,}건/일**

## 3. 분류 정확도

### 이진 분류 (illegal 탐지)
| 지표 | 값 |
|------|---|
| Recall (illegal → T1/T2/T3 탐지) | **{recall_illegal:.2%}** ({illegal_detected_correctly}/{illegal_total}) |
| Specificity (clean → T4 유지) | **{specificity_clean:.2%}** ({clean_kept_clean}/{clean_total}) |

### Tier별 정확도 (gt_tier 기준)
| GT Tier | 정확 분류 | 총 건수 | Accuracy |
|---|---|---|---|
"""
    for tier in ["T1", "T2", "T3", "T4"]:
        c = tier_correct.get(tier, 0)
        t = tier_total.get(tier, 0)
        acc = f"{c/t:.2%}" if t else "-"
        md += f"| {tier} | {c} | {t} | {acc} |\n"

    md += "\n### Tier Confusion Matrix\n\n"
    md += "(행 = ground truth, 열 = predicted)\n\n"
    md += "| GT \\ Pred | T1 | T2 | T3 | T4 |\n|---|---|---|---|---|\n"
    for gt in ["T1", "T2", "T3", "T4"]:
        row = f"| **{gt}** |"
        for pr in ["T1", "T2", "T3", "T4"]:
            row += f" {tier_cm.get((gt, pr), 0)} |"
        md += row + "\n"

    # ============================================================
    # 오분류 샘플 (최대 5건)
    # ============================================================
    mismatches = [r for r in success if r["gt_tier"] != r["pred_tier"]][:5]
    if mismatches:
        md += "\n## 4. 오분류 샘플 (최대 5건)\n\n"
        for r in mismatches:
            md += f"### {r['post_id']} — GT `{r['gt_tier']}` → Pred `{r['pred_tier']}`\n"
            md += f"- **본문**: {r['text']}\n"
            md += f"- **gt_old_type**: `{r['gt_old_type']}` / **pred_type**: `{r['pred_type']}` (conf {r['confidence']:.2f})\n"
            md += f"- **reason_ko**: {r['reason_ko']}\n\n"
    else:
        md += "\n## 4. 오분류 샘플\n\n(없음 — 완벽 분류 또는 success=0)\n"

    # ============================================================
    # 실패 케이스
    # ============================================================
    if failed:
        md += "\n## 5. 실패 케이스\n\n"
        for r in failed:
            md += f"- `{r['post_id']}` — {r['error']}\n"

    # ============================================================
    # 한계 + 본 구현 권장
    # ============================================================
    md += f"""
## 6. 본 SPIKE의 한계

- **이미지 첨부 0건**: `manual_label_set_v1.csv`가 텍스트 전용. 멀티모달 이미지 분석은 검증 안 됨 → Story 3-3 본 구현 시 실 크롤 데이터(`crawler/output/posts/*/images/`)로 별도 spot-check 필요.
- **외국어 0건**: 라벨셋이 한국어 only. `translated_text_ko` 동작 검증 안 됨 → 크롤러의 zh-CN/zh-TW 게시글로 별도 spot-check 필요.
- **신규 type enum 부분 커버**: 라벨셋 type은 `핵_배포 / 매크로_판매 / 리세마라 / 계정_거래 / 기타` 5종. 신규 enum의 `사설서버 / 현금화 / 광고_도배`는 미검증. 라벨셋 v2 (≥300건, Tier별 ≥75) 작성 시 보강.
- **`핵_배포` 모호성**: 신규 enum에서 `핵_치트`(도구 자체) vs `불법프로그램_배포`(매크로·봇 등 도구 배포)로 분리됐으나 구 라벨셋의 `핵_배포`는 둘 다 포함 가능. 본 SPIKE에서는 두 신규 type 모두 T1이라 Tier 매칭에는 무관.

## 7. 본 구현 권장값 (Story 3-3 입력)

| 항목 | 권장 |
|------|------|
| 모델 | `{MODEL}` (본 SPIKE 검증값) |
| response_format | `json_schema` strict mode |
| Schema 필드 | `type, confidence, reason_ko, translated_text_ko, image_observed` |
| Tier 매핑 | 코드에서 결정 (LLM type → Tier — `tier_router.py`) |
| 일일 비용 cap 초기값 | `${5:.0f}` (= ~{int(5 / max(0.0001, avg_cost)):,}건 처리 여유) |
| Worker 동시성 초기값 | 1 (실 운영에서 rate limit/예산으로 조정) |
| 타임아웃 | {int(TIMEOUT_SEC)}s |

## 8. 다음 단계

1. 라벨셋 v2 작성 (`manual_label_set_v2.csv` ≥300건, Tier별 ≥75, 이미지 ≥50, 외국어 ≥30) — QA 트랙
2. Story 3-2 review 코드 정리 (translate.py 삭제, 재사용 부품 추출)
3. Story 3-3 본 구현 착수 — `detection/src/pipeline/llm_classifier.py` + `llm_client.py` + `tier_router.py` + `cost_cap.py`
4. 이미지·외국어 spot-check 통합 (실 크롤 데이터 활용)
5. NC AI 보고 + 법무 검토(이미지 PII) + 운영팀 협의(T1 알림 채널) 병행

---

**원자료**: `{RAW_PATH.relative_to(PROJECT_ROOT)}` (JSONL, 1행 1샘플)
"""

    REPORT_PATH.write_text(md, encoding="utf-8")
    RAW_PATH.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    print(f"\n[OK] 보고서: {REPORT_PATH}")
    print(f"[OK] 원자료: {RAW_PATH}")
    print(f"\n=== 요약 ===")
    print(f"  성공/실패: {len(success)}/{len(failed)}")
    print(f"  illegal recall: {recall_illegal:.2%}")
    print(f"  clean specificity: {specificity_clean:.2%}")
    print(f"  총 비용: ${total_cost:.4f}")
    print(f"  게시글당 평균: ${avg_cost:.4f}")
    print(f"  p95 latency: {p95_latency:.2f}s")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
