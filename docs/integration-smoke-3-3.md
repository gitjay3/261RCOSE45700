# Story 3-3 실사 통합 smoke

**일자**: 2026-05-27
**Story**: 3-3 OpenAI 멀티모달 LLM 분류 + Tier 라우팅
**AC**: #10 (실사 통합 smoke)

## 실행 결과 (실제 OpenAI 호출)

```
$ python detection/scripts/smoke_integration.py
[INFO] model=gpt-4o
[INFO] key=...BGQA (length=164)
[INFO] 큐 적재 완료: posts:queue len=1
{"timestamp": "2026-05-27T06:39:48.151744Z", "service": "crawler", "level": "DEBUG", "correlation_id": "", "message": "cost recorded — model=gpt-4o cost=$0.00197 cumulative=$0.0020"}
{"timestamp": "2026-05-27T06:39:48.151876Z", "service": "crawler", "level": "INFO", "correlation_id": "smoke-cid-001", "message": "classification — type=핵_치트 tier=T1 conf=0.950 cost=$0.00197 tokens(in/out)=537/63 image_observed=False"}
{"timestamp": "2026-05-27T06:39:48.152194Z", "service": "crawler", "level": "INFO", "correlation_id": "smoke-cid-001", "message": "메시지 처리 완료"}
[INFO] run_once returned: True

=== 상태 ===
  posts:queue       : 0 (0이어야 함)
  posts:processing  : 0 (0이어야 함)
  posts:dlq         : 0 (0이어야 함)
  llm:rate_limit    : 사용됨 (TokenBucket acquire 호출)

[DONE] Story 3-3 실사 통합 smoke 통과 — 1건이 큐 → LLM → ACK까지 흘렀습니다.
```

## 검증된 흐름

| 단계 | 결과 |
|---|---|
| 큐 적재 (`posts:queue` LPUSH) | OK (len=1) |
| QueueConsumer.run_once → BRPOPLPUSH | OK (메시지 소비) |
| CostCap.check_and_hold | OK (cap 미달, sleep 없음) |
| TokenBucket.acquire (LLM rate limit) | OK (Lua atomic acquire) |
| LLMClient.classify (실 OpenAI gpt-4o 호출) | OK (537 in / 63 out tokens) |
| `response_format=json_schema` strict | OK (구조화 출력 파싱) |
| LLMClassifier 9-type enum + confidence 검증 | OK |
| TierRouter.route("핵_치트") → T1 | OK |
| CostCap.record → 누적 $0.0020 | OK |
| 구조화 로그 출력 (correlation_id + service + tier + cost) | OK |
| LREM (ACK) → `posts:processing` 비움 | OK |
| DLQ 미사용 | OK |

## 본 smoke의 의미

- production 코드 경로 그대로 사용 (`detection/src/main.py`의 wiring과 동일).
- Redis만 `fakeredis` in-memory로 치환하여 Docker/외부 인프라 없이도 검증 가능.
- **실제 OpenAI 호출**이 발생하여 LLMClient → response 파싱 → 비용 산출 → Tier 라우팅 → ACK까지 1건이 완전히 흘렀음을 증명.
- 비용 $0.00197/post — SPIKE 3.0 baseline($0.0019)과 일치, PRD 목표 ≤ $0.005 통과.

## 운영(Docker + 실 Redis) 모드 — 운영자가 1회 수행 권장

```bash
# 1. Redis 띄우기 (compose 또는 호스트)
docker compose -f infra/docker-compose.yml up -d redis

# 2. infra/.env 확인 — OPENAI_API_KEY 본인 키 입력 완료
grep "^OPENAI_API_KEY=" infra/.env

# 3. 큐에 1건 적재
python detection/scripts/seed_one_post.py --text "리니지M 월핵 팝니다 텔레그램 @test"

# 4. detection main 실행 (1건 소비 후 Ctrl+C)
python -m detection.src.main

# 5. 상태 확인
redis-cli -n 0 LLEN posts:queue        # 0
redis-cli -n 0 LLEN posts:processing   # 0
redis-cli -n 0 LLEN posts:dlq          # 0
```

운영 모드는 외부 Redis가 추가로 검증된다는 점을 빼면 본 smoke와 동일한 흐름이다.
crawler까지 묶은 end-to-end는 Story 5-4(e2e 데모)에서.
