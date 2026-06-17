# AI 검증 과정 운영 가이드

탐지 상세 페이지의 "AI 검증 과정" 패널 해석 방법과 운영 판단 기준을 정리한 문서.

---

## 배경

agentic 모드(`DETECTION_MODE=agentic`)에서 처리된 탐지는 단계별 실행 기록(`agent_runs`)이 저장된다. 단일 호출 모드(`single`)로 처리된 이전 탐지는 "단계별 검증 로그가 저장되어 있지 않습니다" 메시지가 표시된다.

---

## 패널 구성

### 1. 상단 요약 카드 (4개)

| 카드 | 의미 |
|---|---|
| AI 판단 | S1 트리아지 에이전트가 분류한 탐지 유형 (핵_치트, 계정_거래 등) |
| 신뢰도 | S1 트리아지의 0~1 신뢰도. **최종 판단 신뢰도와 다를 수 있다** (S3 Synthesizer 완료 전) |
| 본문 링크 | S0 Normalizer가 게시글 본문에서 추출한 외부 링크 수 |
| 위험 링크 | S2b LinkTracer가 실제 접속해 배포·판매 정황을 확인한 링크 수 |

위험 링크가 1개 이상이면 빨간 배너와 함께 가장 위험한 링크 URL을 표시한다.

### 2. 단계별 타임라인

단계는 실행 순서대로 나열된다. 각 단계를 클릭하면 세부 결과가 펼쳐진다.

| 단계 | 표시 이름 | 내용 |
|---|---|---|
| `normalize` | 정리 | 변형문자·숨김문자 제거, 본문에서 외부 링크 목록 추출 |
| `triage` | 판단 | gpt-4o-mini가 유형 분류 + 신뢰도 산출. "외부 링크 확인 필요"/"이미지 확인 필요" 표시 |
| `link_trace` | 링크 | 외부 링크를 1-hop fetch해 배포·판매 정황 확인. **위험 근거가 있으면 자동으로 펼쳐진다** |
| `image` | 이미지 | (Story 3-8 구현 예정) 이미지 분석 결과 |
| `synthesize` | 결론 | (Story 3-8 구현 예정) 모든 증거를 종합한 최종 판단 |

---

## 링크 단계 세부 해석

각 링크 카드에 표시되는 항목:

| 항목 | 설명 |
|---|---|
| 링크 유형 | `일반 웹 링크` / `메신저 채널` / `파일 다운로드 링크` / `열람 차단` / `확인 오류` |
| 위험 근거 배지 | `is_distribution_site=true`일 때 표시. 배포·판매 정황이 감지됨 |
| indicators | 실제 감지된 지표 텍스트 ("배포 관련 표현 발견", "거래/연락처 정황 발견") |
| 확인 상태 | `접속 확인` / `메신저 링크라 열람 생략` / `안전 정책으로 차단` / `페이지 없음` / `접속 실패` |

### `is_distribution_site` 판정 기준 요약

**LLM 미사용, 규칙 기반.** 페이지 제목과 본문에서 아래 중 하나라도 감지되면 `true`.

- 배포 키워드: `download`, `다운로드`, `下载`, `crack`, `破解`, `外掛`, `hack`, `cheat`, `핵`, `매크로`, `bot` 등
- 거래/연락처 키워드: `가격`, `판매`, `代儲`, `面交`, `price`, `paypal`, `wechat` 등
- 금액 패턴: `10,000원`, `5만원` 형태

**예외 (판정 안 함):**
- 메신저 초대링크 (discord.gg, t.me, open.kakao.com 등): fetch 없이 `kind=messenger` 기록만
- 공식 도메인 + 설치 문맥 (plaync.com, steampowered.com, play.google.com 등에 런처·스토어 키워드): `false`로 예외

전체 키워드 목록과 공식 도메인 목록은 [detection/README.md](../detection/README.md#linkttracer-배포-판단-기준) 참조.

---

## 운영자 판단 흐름

```
위험 링크 N개 배너 확인
  ├─ N = 0 → 링크 경로 배포 정황 없음. 트리아지 신뢰도와 유형으로 판단
  └─ N ≥ 1 → 위험 링크 카드 확인
       ├─ kind=messenger → 메신저 채널 유도. 채널 직접 확인 권장
       ├─ kind=web, is_distribution_site=true → 배포·판매 페이지 직접 접속 확인
       └─ kind=file_direct_link → 파일 다운로드 링크 발견. 즉시 조치 검토
```

---

## 기술 로그 읽기

각 단계 펼침 하단에 표시되는 기술 로그:

```
기술 로그: gpt-4o-mini · 537tok · 3.2s
```

| 항목 | 의미 |
|---|---|
| 모델명 | 해당 단계에서 호출한 LLM. `LLM 미사용`이면 규칙 기반(link_trace, normalize) |
| tok | 입력 + 출력 토큰 합계 |
| 응답 시간 | 단계 처리 소요 시간 |

원본 JSON은 상단 "원본 로그" 링크 (`GET /api/detections/{id}/agent-runs`)에서 확인 가능.

---

## 관련 파일

| 역할 | 파일 |
|---|---|
| LinkTracer 판단 기준 (상세) | [detection/README.md](../detection/README.md) |
| LinkTracer 구현 | [detection/src/agents/link_tracer.py](../detection/src/agents/link_tracer.py) |
| 공식 도메인 예외 정책 | [detection/src/agents/url_policy.py](../detection/src/agents/url_policy.py) |
| 대시보드 UI 컴포넌트 | [dashboard/src/components/tracker/AgentRunTrace.tsx](../dashboard/src/components/tracker/AgentRunTrace.tsx) |
| DB 스키마 (agent_runs) | [api/src/main/resources/db/migration/V10__agent_runs.sql](../api/src/main/resources/db/migration/V10__agent_runs.sql) |
| agentic 모드 smoke 결과 | [docs/integration-smoke-3-7.md](integration-smoke-3-7.md) |
