# Architecture Decision Records

이 폴더는 본 프로젝트의 의미 있는 기술적·아키텍처 의사결정을 시간 순으로 기록합니다.
ADR 형식은 [MADR](https://adr.github.io/madr/) 변형을 따릅니다.

## ADR 인덱스

| 번호 | 제목 | 상태 | 결정일 |
|---|---|---|---|
| [0001](./0001-secret-management-strategy.md) | 시크릿 관리 전략 — Docker secrets + EC2 SSH 수동 작성 채택 | Accepted | 2026-05-12 |

## 상태 (Status) 정의

- **Proposed**: 제안 단계, 합의 전
- **Accepted**: 채택되어 적용 중
- **Deprecated**: 더 이상 권장하지 않음 (대체재 없음)
- **Superseded by ADR-XXXX**: 새 ADR로 대체됨

## 새 ADR 작성

새 결정을 기록하려면 `/decision-logger:log` 슬래시 커맨드를 사용하세요.
- 파일명: `{NNNN}-{kebab-case-title}.md` (4자리 시퀀스, 영문 kebab-case)
- 신규 ADR 작성 시 본 인덱스 표에 한 줄 추가
- 기존 ADR을 대체하는 결정이면 기존 ADR 상태를 `Superseded by ADR-NNNN`으로 갱신
