"""OpenAI 키·네트워크·모델 가용성 smoke test.

Sprint Change Proposal 2026-05-27 Step 1.
SPIKE 3.0 진입 전 검증용. 1회 chat completions 호출로 다음을 확인:
- infra/.env에서 OPENAI_API_KEY 로딩 성공
- 네트워크 + OpenAI API 도달 가능
- 지정 모델(LLM_MODEL, 기본 gpt-4o) 호출 성공
- response_format=json_schema 구조화 출력 동작

Usage (프로젝트 루트에서):
    pip install -r detection/requirements.txt
    python detection/scripts/smoke_openai.py

키 안전:
- .env는 .gitignore되어 커밋되지 않음
- 본 스크립트는 키를 절대 로깅·출력하지 않음 (마지막 4자리만 표시)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# infra/.env 로드 (프로젝트 루트 또는 detection/에서 실행 모두 지원)
try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("[FAIL] python-dotenv 미설치. `pip install -r detection/requirements.txt` 먼저 실행.")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / "infra" / ".env"

if not ENV_PATH.exists():
    sys.exit(f"[FAIL] {ENV_PATH} 없음. `cp infra/.env.example infra/.env` 후 OPENAI_API_KEY 입력.")

load_dotenv(ENV_PATH)

api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key or api_key.startswith("sk-REPLACE"):
    sys.exit(
        "[FAIL] OPENAI_API_KEY가 placeholder입니다. "
        f"{ENV_PATH}를 열어 본인 키(sk-...)로 교체하세요."
    )

model = os.environ.get("LLM_MODEL", "gpt-4o")
timeout = float(os.environ.get("LLM_TIMEOUT_SEC", "30"))

# 키는 마지막 4자리만 표시 (전체 노출 금지)
print(f"[INFO] env: {ENV_PATH}")
print(f"[INFO] OPENAI_API_KEY: ...{api_key[-4:]} (length={len(api_key)})")
print(f"[INFO] LLM_MODEL: {model}")
print(f"[INFO] LLM_TIMEOUT_SEC: {timeout}")

try:
    from openai import OpenAI
except ImportError:
    sys.exit("[FAIL] openai SDK 미설치. `pip install -r detection/requirements.txt` 실행.")

client = OpenAI(api_key=api_key, timeout=timeout)

# 게임 도메인 미니 테스트: 한국어 응답 + JSON schema 구조화 출력 + Tier 매핑까지 한 번에 검증
system_prompt = (
    "당신은 게임 보안 분석가입니다. 주어진 게시글의 불법성을 판단하고, "
    "type, tier, confidence, reason_ko, translated_text_ko를 JSON으로 반환합니다. "
    "type enum: 핵_치트 | 사설서버 | 불법프로그램_배포 | 계정_거래 | 매크로_판매 | 리세마라 | 현금화 | 광고_도배 | 기타. "
    "tier: T1(핵_치트/사설서버/불법프로그램_배포), T2(계정_거래/매크로_판매), T3(리세마라/현금화/광고_도배), T4(기타). "
    "한국어 외 본문은 translated_text_ko에 한국어 번역, 한국어 원문은 null. "
    "reason_ko는 항상 한국어."
)

test_post = "리니지M 핵 팝니다. 즉시 사용 가능. 텔레그램 @hack_seller_test"

schema = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "tier": {"type": "string", "enum": ["T1", "T2", "T3", "T4"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason_ko": {"type": "string"},
        "translated_text_ko": {"type": ["string", "null"]},
    },
    "required": ["type", "tier", "confidence", "reason_ko", "translated_text_ko"],
    "additionalProperties": False,
}

print(f"\n[INFO] 호출 중... (model={model})")
try:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"게시글:\n{test_post}"},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "tracker_classification",
                "strict": True,
                "schema": schema,
            },
        },
    )
except Exception as e:
    sys.exit(f"[FAIL] OpenAI 호출 실패: {type(e).__name__}: {e}")

content = resp.choices[0].message.content
usage = resp.usage

print("\n[OK] 응답 수신 성공")
print(f"  - model: {resp.model}")
print(f"  - input tokens : {usage.prompt_tokens}")
print(f"  - output tokens: {usage.completion_tokens}")
print(f"  - total tokens : {usage.total_tokens}")

try:
    parsed = json.loads(content)
    print("\n[OK] JSON schema 구조화 출력 파싱 성공")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
except json.JSONDecodeError as e:
    print(f"\n[WARN] JSON 파싱 실패: {e}")
    print(f"raw content: {content}")
    sys.exit(1)

# 검증 — 예상값(핵_치트 / T1)에 가까운지
expected_type = "핵_치트"
expected_tier = "T1"
got_type = parsed.get("type")
got_tier = parsed.get("tier")

if got_tier == expected_tier:
    print(f"\n[OK] Tier 예상 일치: {got_tier}")
else:
    print(f"\n[WARN] Tier 예상 불일치: expected={expected_tier}, got={got_tier} (프롬프트 튜닝 필요 가능성)")

if got_type == expected_type:
    print(f"[OK] Type 예상 일치: {got_type}")
else:
    print(f"[INFO] Type: expected={expected_type}, got={got_type} (큰 문제 아님 — 유사 카테고리도 허용)")

print("\n[DONE] smoke test 통과. SPIKE 3.0 진행 가능.")
