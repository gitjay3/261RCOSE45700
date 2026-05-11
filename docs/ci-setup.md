# CI / Branch Protection Setup

Story 1.5의 GitHub Actions 워크플로우 4종은 서브시스템별 lint/test/build를
자동 실행합니다. Story 5.2가 strict required check를 `ci.yml` aggregator
워크플로로 추가했고, 자동 배포 통로(`deploy.yml`)도 같은 reusable workflow를
재사용합니다.

> **Story 5.2 시점 갱신**: 본 문서가 정의했던 "Story 5.2 Strict" 단계가
> 실제 코드로 들어왔습니다. Story 1.5 시점의 deferred 항목(strict required
> check)은 아래 [§Story 5.2 변경](#story-52-aggregator--배포-게이트-추가) 참조.

## 워크플로우 4종

| 파일 | Job | 트리거 경로 |
|---|---|---|
| `.github/workflows/crawler.yml` | `lint-test` | `crawler/**`, `shared/**` |
| `.github/workflows/detection.yml` | `lint-test` | `detection/**`, `shared/**` |
| `.github/workflows/api.yml` | `lint-test` | `api/**` |
| `.github/workflows/dashboard.yml` | `lint-test` | `dashboard/**` |

각 워크플로우는 자기 파일(`.github/workflows/*.yml`) 변경 시에도 트리거됩니다.

## Branch Protection 절차 (Story 5.2 Strict)

1. GitHub repo → **Settings** → **Branches**
2. **Branch protection rules** → **Add rule** (또는 기존 `main` 규칙 편집)
3. **Branch name pattern**: `main`
4. 다음 옵션 활성화:
   - ☑ **Require a pull request before merging** (1 approval)
   - ☑ **Require status checks to pass**
     - Required: **`ci / aggregator`** (단일 strict gate — 4개 서브시스템 결과를 합산)
     - 옵션: `deploy / deploy` (배포 실패 시 후속 PR 차단)
   - ☑ **Do not allow bypassing the above settings**
   - **Allow auto-merge: OFF** (자동 배포와 충돌 방지)

> Story 1.5 MVP에서는 path-filtered workflow의 pending 문제로 strict required
> check 등록을 보류했습니다. Story 5.2가 `ci.yml` aggregator를 추가하면서
> 단일 진입점이 생겨 이 보류가 해소됐습니다.

## Paths 필터와 Required Status Checks 주의사항

워크플로우에 `paths:` 필터가 있어 **PR이 해당 경로를 건드리지 않으면 워크플로우가
실행되지 않습니다**. GitHub Branch Protection은 실행되지 않은 required check를
"pending"으로 간주해 머지를 블로킹할 수 있습니다.

### Story 5.2 Aggregator 도입

`ci.yml`이 모든 PR + push:main에서 path filter 없이 항상 실행되며, 4개
서브시스템 reusable workflow(`crawler.yml`/`detection.yml`/`api.yml`/
`dashboard.yml`)를 `uses:`로 호출합니다. 마지막 `aggregator` 잡이
`needs: [crawler, detection, api, dashboard]` + `if: always()`로 결과를 합산합니다.

| 워크플로우 | 트리거 | 역할 |
|---|---|---|
| `crawler.yml` / `detection.yml` / `api.yml` / `dashboard.yml` | path filter (PR/push:main) **+** `workflow_call` | 서브시스템별 빠른 lint/test (path 변경 시) |
| `ci.yml` | PR + push:main, **no path filter** | 4개 reusable 호출 + `aggregator` strict gate |
| `deploy.yml` | push:main + `workflow_dispatch` | 같은 reusable 4종 호출 후 GHCR 빌드 + EC2 배포 |

main 머지 1회당 reusable workflow 4종이 두 번 실행되는 비용이 있지만(`ci.yml`
+ `deploy.yml`), 배포 안전성 우선으로 수용합니다.

## 시크릿 관리

- 워크플로우 파일에 평문 키·토큰·비밀번호를 절대 작성하지 않습니다 (NFR5).
- 향후 통합 테스트가 추가되어 외부 API를 호출해야 할 경우, 다음 패턴 사용:

  ```yaml
  - name: Run integration test
    env:
      VARCO_API_KEY: ${{ secrets.VARCO_API_KEY }}
    run: pytest tests/integration
  ```

- GitHub UI → Settings → Secrets and variables → Actions에서 `VARCO_API_KEY` 등록.

## 검증 방법

본 브랜치 push 후 GitHub Actions 탭에서:

1. 어떤 워크플로우가 트리거됐는지 확인 (paths 필터 동작)
2. 변경 경로에 해당하는 워크플로우의 `lint-test` job이 통과했는지 확인
3. 의도적으로 lint 위반 commit을 한 번 push해 빨강 → revert로 검증

## Story 5.2 Aggregator + 배포 게이트 추가

Story 1.5 시점 deferred 항목(strict required check)이 본 스토리에서 다음과 같이 해소:

- `ci.yml` (aggregator) 추가 — 모든 PR/push:main에서 실행, single required check.
- 기존 4개 워크플로에 `workflow_call:` 트리거 추가 (기존 path-filter 트리거와 공존).
- `deploy.yml`이 동일 reusable 4종을 게이트로 호출 — `workflow_dispatch` 우회 시에도 lint-test 재검증.

운영 절차/시크릿/롤백 등 배포 관련 자세한 내용은
[`docs/deployment.md`](./deployment.md) 참조.
