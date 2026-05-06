# CI / Branch Protection Setup

Story 1.5의 GitHub Actions 워크플로우 4종은 서브시스템별 lint/test/build를
자동 실행합니다. PR 머지를 실제로 블로킹하는 strict required check 구성은
path-filtered workflow의 pending check 문제 때문에 Story 5.2에서 aggregator 방식으로
구성합니다.

## 워크플로우 4종

| 파일 | Job | 트리거 경로 |
|---|---|---|
| `.github/workflows/crawler.yml` | `lint-test` | `crawler/**`, `shared/**` |
| `.github/workflows/detection.yml` | `lint-test` | `detection/**`, `shared/**` |
| `.github/workflows/api.yml` | `lint-test` | `api/**` |
| `.github/workflows/dashboard.yml` | `lint-test` | `dashboard/**` |

각 워크플로우는 자기 파일(`.github/workflows/*.yml`) 변경 시에도 트리거됩니다.

## Branch Protection 절차 (Story 1.5 MVP)

1. GitHub repo → **Settings** → **Branches**
2. **Branch protection rules** → **Add rule** (또는 기존 `main` 규칙 편집)
3. **Branch name pattern**: `main`
4. 다음 옵션 활성화:
   - ☑ **Require a pull request before merging**
   - ☑ **Do not allow bypassing the above settings**
5. Story 1.5에서는 4개 path-filtered workflow를 required check로 등록하지 않습니다.
   PR 리뷰어가 변경 경로에 맞는 Actions 결과를 확인합니다.

## Paths 필터와 Required Status Checks 주의사항

워크플로우에 `paths:` 필터가 있어 **PR이 해당 경로를 건드리지 않으면 워크플로우가
실행되지 않습니다**. GitHub Branch Protection은 실행되지 않은 required check를
"pending"으로 간주해 머지를 블로킹할 수 있습니다.

대응 방향:

- **Story 1.5 MVP**: 4 워크플로우를 required로 등록하지 않고, PR 리뷰어가 각 status를
  수동 확인합니다.
- **Story 5.2 Strict**: 모든 PR에서 항상 실행되는 `ci-aggregator.yml` 메타 워크플로우를
  추가하고, aggregator check만 required로 등록합니다. 4 워크플로우는 path filter로 실제
  일을 하고 aggregator가 결과를 합산합니다.

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
