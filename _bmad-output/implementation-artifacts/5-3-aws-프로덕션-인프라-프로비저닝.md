# Story 5.3: AWS 프로덕션 인프라 프로비저닝 (학생 계정 사양)

Status: closed (ClickOps demo)

> **2026-05-06 PIVOT (최종) — Terraform IaC 자체 폐기, ClickOps로 전환.**
>
> 학생 IAM 사용자(`arn:aws:iam::<aws-account-id>:user/<student-iam-user>`)에서 다음 통로가 모두 차단됨이 확인됨:
> 1. **IAM Access Key 발급 차단** (`iam:ListAccessKeys` 권한 거부, 2026-05-04 확인) — 로컬 머신에서 `aws configure` 사용 불가
> 2. **CloudShell explicit deny** (`cloudshell:CreateEnvironment`, 2026-05-06 확인) — 콘솔 안에서 셸 사용 불가
> 3. **IAM Role 생성 차단** (학생 본인 확인) — GitHub Actions OIDC + AssumeRole 통로도 불가
>
> Terraform이 AWS API를 호출할 자격증명 통로가 0개로 학생 권한 변경 없이는 apply 자체가 불가능. 학교 관리자에게 권한 요청은 옵션 외이므로 IaC 시도 종료. `infra/terraform/` + lint configs + workflow 일괄 제거 (commit `13d96a9`). 데모는 콘솔 ClickOps + 스크린샷으로 진행하며, 코드는 git history(`b7e24d3`, `bd172d9`, `3b98a13` 등)에 보존되어 졸업 후 개인 계정에서 동일 인프라 재현 가능.
>
> ---
>
> **2026-05-04 PIVOT (1차) — 학생 계정 제약에 맞춰 architecture 전면 재설계.** _[기록 보존]_
> 기존 production-grade IaC (PR #18 기준 r6g/t4g + custom VPC + CloudTrail/KMS CMK/Budgets) 결정을
> 학생 계정 SCP 제약에 맞춰 다운그레이드. `(A2) 트랙` 채택. 코드/CI/문서 모든 측면 완료, 실 apply는 별도 ops 세션 deferred. 이후 2026-05-06 ClickOps PIVOT으로 코드 제거됨 — 아래 AC/Tasks/Dev Notes는 **IaC 코드 작성 노력의 기록**이며 실제 인프라는 ClickOps로 재구축됨.

## 최종 결과 요약 (2026-05-06)

| 항목 | 결과 |
|---|---|
| AC #1~24 (코드 측면) | ✅ Terraform 코드로 정의·검증 완료 (`fmt`/`validate`/TFLint/Checkov 정적 가드 모두 통과) — git history 보존 |
| 실 인프라 프로비저닝 | ⛔ Terraform apply 불가 → **ClickOps로 전환** |
| 데모 자료 | ClickOps로 만든 자원 스크린샷 + 콘솔 화면 캡처 |
| 졸업 후 재현성 | 개인 AWS 계정에서 git history 복구 → `terraform apply` 한 방으로 동일 인프라 재현 가능 |

발표 시 설명: "프로덕션 환경에선 IaC가 표준이고 우리도 그렇게 작성했지만, 학생 계정 SCP 제약(IAM Access Key + CloudShell + IAM Role 생성 모두 차단)으로 실 apply 불가능 → ClickOps로 데모. 코드는 졸업 후 개인 계정에서 그대로 재현 가능."

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

인프라 담당자로서,
AWS EC2·RDS·S3·보안 그룹이 Terraform 코드로 프로덕션 환경에 맞게 구성되기를 원한다,
그래서 시스템이 안전하게 운영 가능한 상태로 배포되며 인프라 변경이 PR 리뷰를 거친다.

## Acceptance Criteria

> **PIVOT 2026-05-04 — 학생 계정 제약에 맞춰 AC 다수 갱신.**
> 변경 사유: AWS 콘솔에서 직접 확인된 SCP 제약 — EC2는 t3.{nano,micro,small,medium} 4종 한정 / RDS는 MySQL+postgres만 + 샌드박스 템플릿 + Default VPC 강제 + publicly_accessible 강제. 추가 보수 가정: CloudTrail/KMS CMK/Budgets는 학생 계정 권한 부족 가정 → 코드에서 제외.

1. **Given** 학생 AWS 계정(`학생 계정`)과 IAM 권한이 준비된 상태에서 **When** 인프라 프로비저닝이 완료되면 **Then** 모든 가능한 AWS 리소스가 `infra/terraform/` 코드로 정의되며 Console 수동 생성(ClickOps)이 금지된다 (학생 계정 SCP로 코드 정의가 차단되는 항목은 deferred-work에 명시)
2. **And** Terraform `>= 1.14, < 2.0` + AWS provider `~> 6.0`이 명시적으로 핀되며, `terraform-aws-modules/rds/aws ~> 7.2` · `ec2-instance/aws ~> 6.4` · `security-group/aws ~> 5.3` 공식 모듈 버전이 모두 핀된다 (`vpc/aws` 모듈은 default VPC 사용으로 미사용)
3. **And** Crawler EC2(**t3.medium**, 2vCPU/4GB, x86_64), Detection EC2(**t3.medium**, 2vCPU/4GB, x86_64), API EC2(**t3.medium**, 2vCPU/4GB, x86_64) **3개 인스턴스가 각각 분리된 보안 그룹으로 구성**되며, AMI는 Amazon Linux 2023 x86_64로 명시 선택된다. 학생 계정의 t3 4종 한정 + Graviton(arm64) 미가용 제약 반영. Crawler RAM 16GB → 4GB 다운그레이드는 Story 5.4 부하 측정 후 재검토(deferred-work)
4. **And** RDS PostgreSQL **16.13** db.t3.micro **Single-AZ + automated backup 7일 + 샌드박스 템플릿** 설정으로 프로비저닝된다. 학생 계정 SCP가 `publicly_accessible=true`를 강제하므로 **퍼블릭 액세스 허용 + 보안 그룹으로 1차 방어**(inbound 5432 source = EC2 SG IDs only) + parameter group `rds.force_ssl=1`로 평문 접속 차단
5. **And** Redis(docker-compose on API EC2) 6379 포트가 외부 접근을 차단하고 API EC2 보안 그룹 내부에서만 접근된다 (NFR7)
6. **And** S3 버킷 정책이 퍼블릭 접근을 차단하고(`block_public_acls=true`, `block_public_policy=true`) Crawler EC2 IAM Role에만 쓰기 권한을 부여한다. VPC Gateway Endpoint(S3)는 default VPC 라우팅에 추가하면 충돌 가능성으로 본 스토리에서 제외(deferred-work)
7. **And** 각 EC2에 IAM Instance Role이 부여되어 AWS SDK가 환경변수 Access Key 없이 동작한다 (NFR6)
8. **And** **EC2 접근은 SSM Session Manager**를 통해 이루어지며, 외부 22번 포트는 보안 그룹에서 완전 차단된다(SSH 키 미사용). 각 EC2 IAM Role에 `AmazonSSMManagedInstanceCore` AWS 관리형 정책이 연결된다 (NFR6 + NFR7)
9. **And** EBS 볼륨은 region default 암호화 정책을 따른다. `aws_ebs_encryption_by_default` 자원은 학생 계정에서 권한 부족 가능성으로 코드 미포함 — 콘솔 1회 enable 또는 학교 default 정책에 의존(deferred-work)
10. **And** **VPC Flow Logs**는 default VPC에 추가하면 학생 계정 권한 부족 가능성으로 본 스토리에서 제외(deferred-work) — 학교 default 정책 또는 콘솔 1회 enable로 보강
11. **And** AWS CloudTrail은 학생 계정 권한 부족 가정으로 본 스토리에서 코드 제외(deferred-work) — 학교 organization trail이 있다면 그것에 의존
12. **And** `infra/terraform/bootstrap/`을 1회 apply하여 state 백엔드(S3 버킷 `tracker-tfstate-{env}` + 서버사이드 암호화 SSE-S3 + 버전 관리 + native locking `use_lockfile = true`, **별도 DynamoDB 테이블 불필요**)가 생성된다. KMS 제약 가능성으로 SSE-S3 폴백
13. **And** `infra/terraform/environments/dev/`만 학생 계정 적용으로 활성. `environments/prod/`는 portfolio용으로 코드 보존하되 실 apply 안 함(README 명시) — 학생 계정 1개로 prod 환경 분리 의미 없음
14. **And** EC2·RDS·Security Group은 `terraform-aws-modules/{ec2-instance,rds,security-group}/aws` 공식 검증 모듈을 우선 사용한다. VPC는 default VPC `data` source로 lookup하며 `vpc/aws` 모듈은 미사용
15. **And** 시크릿(`VARCO_API_KEY` 등)은 AWS Secrets Manager에 저장되며 `tfvars`/`tfstate`에 평문으로 포함되지 않는다 (NFR5). KMS는 AWS-managed key(`alias/aws/secretsmanager`) 사용
16. **And** pre-commit hook은 `antonbabenko/pre-commit-terraform` 표준 저장소의 hook(`terraform_fmt`, `terraform_validate`, `terraform_tflint`, `terraform_checkov`, `terraform_docs`)을 사용하며, 모듈별 `README.md`의 Inputs/Outputs 표가 `terraform-docs`에 의해 자동 생성·갱신된다
17. **And** PR에서 `terraform fmt`·`terraform validate`·TFLint·Checkov가 GitHub Actions로 자동 실행되며, 1건 이상 실패 시 머지가 차단된다
18. **And** GitHub Actions ↔ AWS 인증은 OIDC + IAM Role(`aws_iam_openid_connect_provider`)로 처리되어 장기 Access Key가 GitHub Secrets에 저장되지 않는다 (NFR6) — 학생 계정에서 IAM OIDC provider 생성 권한 가정
19. **And** 학교가 사전 설정한 AWS Budget을 활용한다(예: $50~100/월 한도). `aws_budgets_budget` 자원은 학생 계정 권한 부족 가능성으로 본 스토리에서 제외 — Cost Explorer로 사후 모니터링(deferred-work)
20. **And** PR에서 `terraform plan` 결과가 자동으로 PR 코멘트에 게시되며, dev 환경 `apply`는 main 머지 시 자동 실행된다. prod 환경 apply는 본 스토리 범위 외 (학생 계정에서 prod 미운영)
21. **And** `infra/DATA_POLICY.md`에 수집 데이터의 탐지 목적 전용 사용 방침과 외부 공개 금지 정책이 문서화된다 (NFR9)
22. **And** Terraform 모듈·환경 사용법, bootstrap 절차, drift 점검 가이드, **학생 계정 제약 + 보안 trade-off**가 `infra/terraform/README.md`에 문서화된다
23. **And** **NAT 운영 방식: NAT 없음** — Default VPC가 IGW를 자동 제공하며 EC2 3종이 public subnet에 자동 배치된다. EC2 SG는 외부 inbound 0개(crawler/detection) 또는 80/443만(api)으로 차단
24. **And** RDS는 publicly_accessible=true(학생 계정 강제)이지만 SG inbound 5432 source = {detection-sg, api-sg} 한정으로 인터넷에서는 SG 차단으로 접근 불가. 추가로 `rds.force_ssl=1` parameter group으로 TLS만 허용 (NFR7 보안 보강)

## Tasks / Subtasks

> **선행 결정 사항 (PR #18, [bd172d9](https://github.com/byungju0/261RCOSE45700/commit/bd172d9))**
> SPIKE 5.0 결과는 별도 `docs/infrastructure-design.md`로 만들지 않고 `architecture.md` Infrastructure & Deployment 섹션 + `epics.md` Epic 5 + `tracker_기획서.md` 10.1로 backport되어 있음. 본 스토리는 그 결정값을 코드로 옮긴다.
>
> **NAT 운영 방식 결정 (SPIKE 5.0 #11, 2026-05-04 확정):**
> - **선택: public subnet only — NAT 없음** ($0/월)
> - **근거:** 학생 프로젝트 11주 + 30만원 예산. 인바운드는 모든 EC2에서 보안 그룹으로 0개 차단(SSM Session Manager가 outbound로 접속 처리), Checkov CI 게이트가 SG 실수 자동 차단. 보안 그룹만 잘 잠그면 NAT 뒤 private subnet과 사실상 동등한 보안 수준이며 NFR7(RDS/Redis는 VPC 내부망)은 RDS만 private subnet에 두는 것으로 만족.
> - **확장 여지:** Terraform 변수 `nat_strategy = "none" | "instance" | "gateway"`로 모듈 분기 보존. 발표 데모 직전 또는 트래픽 증가 시 `instance`(fck-nat) 또는 `gateway`로 전환 가능.
> - **수용 트레이드오프:** EC2가 public IP 보유 → Checkov `CKV_AWS_88`(EC2 퍼블릭 IP 비할당) 위반 → `.checkov.yml`에 skip 사유 명시(architecture.md Infrastructure & Deployment 결정 근거 인용).
>
> **EC2 접근/관리 백업 방식 (SPIKE 5.0 #12):**
> - 본 스토리는 SSM Session Manager 단독으로 구현하고, 한계 식별 시 deferred-work에 기록.

### Task 1: Bootstrap (state 백엔드 1회성 생성) (AC: #12)

- [x] 1.1 `infra/terraform/bootstrap/main.tf` 작성 — S3 버킷 `tracker-tfstate-${var.env}` (서버사이드 암호화 `aws:kms`, 버전 관리 활성, 퍼블릭 접근 4종 차단)
- [x] 1.2 `infra/terraform/bootstrap/variables.tf` — `env` (dev | prod), `region` (기본값 ap-northeast-2)
- [x] 1.3 `infra/terraform/bootstrap/README.md` — "1회 apply 후 state는 로컬에 보관, 이후 절대 destroy 금지" 절차 명시
- [ ] 1.4 dev/prod 각각 `terraform init && terraform apply`로 state 버킷 생성 검증 — **별도 ops 세션으로 deferred** (Option A 범위)
- [x] 1.5 **DynamoDB lock 테이블 생성하지 않음** — `use_lockfile = true`로 대체 (`environments/{env}/backend.tf`)

### Task 2: Networking 모듈 — Default VPC lookup (PIVOT) (AC: #14, #23)

- [x] 2.1 **PIVOT** — custom VPC 생성 X. `data "aws_vpc" "default"` + `data "aws_subnets" "default"`로 Default VPC lookup
- [x] 2.2 **NAT 없음** — Default VPC에 IGW 기본 존재. 인스턴스 분기 변수 제거
- [x] 2.3 Default VPC의 모든 subnet (학생 계정에선 11 subnet / 6 AZ) 정렬해서 `first_subnet_id` / `second_subnet_id` 노출
- [x] 2.4 VPC Gateway Endpoint(S3) **제거** — Default VPC 라우트 테이블 수정 권한 불확실 (deferred-work)
- [x] 2.5 VPC Flow Logs **제거** — 학생 계정 권한 부족 가정 (deferred-work)
- [x] 2.6 `outputs.tf` — vpc_id, vpc_cidr, subnet_ids, first_subnet_id, second_subnet_id
- [x] 2.7 README — 학생 계정 PIVOT + production 복구 절차 명시

### Task 3: Security Group 모듈 (서비스별 격리) (AC: #4, #5, #8, #14)

- [x] 3.1 `infra/terraform/modules/security-groups/main.tf` 작성 — `terraform-aws-modules/security-group/aws ~> 5.3` 4회 호출
- [x] 3.2 **Crawler SG**: outbound 443 + 80, inbound 0
- [x] 3.3 **Detection SG**: outbound 443(VARCO/AWS) + 5432→RDS SG (`aws_vpc_security_group_egress_rule`로 referenced_security_group_id), inbound 0
- [x] 3.4 **API SG**: inbound 80/443 + 6379 self-reference, egress all
- [x] 3.5 **RDS SG**: inbound 5432 from {detection-sg, api-sg} only (`computed_ingress_with_source_security_group_id`), egress none
- [x] 3.6 모든 SG inbound 22 미정의 — Checkov CKV_AWS_24/25 통과

### Task 4: IAM 모듈 (Instance Role + SSM + GitHub OIDC) (AC: #7, #8, #18)

- [x] 4.1 `infra/terraform/modules/iam/main.tf` 작성
- [x] 4.2 EC2 Role 3종 — `AmazonSSMManagedInstanceCore` attach + `aws_iam_instance_profile` 3종
- [x] 4.3 Crawler Role S3 PutObject — `archive_bucket_arn` ARN 한정
- [x] 4.4 Detection/API Role Secrets — `secretsmanager:GetSecretValue` + `Describe`, `secrets` 모듈의 detection/api_secret_arns ARN 한정
- [x] 4.5 GitHub OIDC Provider — `create_oidc_provider` 토글로 dev에서만 1회 생성, prod는 `existing_oidc_provider_arn` 참조 (계정당 1개 원칙)
- [x] 4.6 GHA Terraform Role — `github_actions_sub_patterns` 변수로 dev=`ref:refs/heads/main` + `pull_request`, prod=`environment:prod` 매칭
- [x] 4.7 EC2 Instance Role은 모두 ARN 한정 적용. GHA Role의 mutate 정책 일부 service-level write `Resource: "*"`는 Checkov skip(.checkov.yml 사유 명시) + deferred-work 기록

### Task 5: EC2 모듈 — t3.medium x86_64 ×3 (PIVOT) (AC: #3, #7, #8, #23)

- [x] 5.1 `terraform-aws-modules/ec2-instance/aws ~> 6.4` 호출
- [x] 5.2 입력 변수 + `instance_type` validation으로 t3.{nano,micro,small,medium} 4종만 허용
- [x] 5.3 **PIVOT** — `data "aws_ami" "al2023_x86_64"` (Graviton arm64 미가용)
- [x] 5.4 root_block_device — gp3 + region default 암호화
- [x] 5.5 환경별 3회 호출 — crawler/detection/api 모두 **t3.medium** (학생 계정 4종 한정 최대), Default VPC subnet 배치
- [x] 5.6 user_data 공백 (Story 5.2 CD 책임)
- [x] 5.7 IMDSv2 강제 (CKV_AWS_79)
- [x] 5.8 SG 4종 inbound 점검 동일

### Task 6: RDS 모듈 (PostgreSQL 16.13) (AC: #4, #14)

- [x] 6.1 `terraform-aws-modules/rds/aws ~> 7.2`
- [x] 6.2 PostgreSQL 16.13 + **PIVOT: db.t3.micro** (db.t4g.micro arm64 미가용), validation으로 db.t3.{micro,small,medium} 한정
- [x] 6.3 gp3 20GB, `storage_encrypted = true`, `multi_az = false` (샌드박스 템플릿 강제)
- [x] 6.4 backup 7일, window 명시
- [x] 6.5 **PIVOT: `publicly_accessible = true`** (학생 계정 SCP 강제) + RDS SG 결합 + `db_subnet_group_name = "default"` (Default VPC subnet group)
- [x] 6.6 `random_password` → Secrets Manager 주입 + `lifecycle.ignore_changes = [secret_string]`
- [x] 6.7 dev `deletion_protection=false / skip_final_snapshot=true` (prod 환경은 미사용)
- [x] 6.8 `auto_minor_version_upgrade = true`
- [x] 6.9 **PIVOT 보안 보강 — Custom parameter group `{identifier}-force-ssl` with `rds.force_ssl=1`** TLS만 허용 → publicly_accessible=true 보안 보강

### Task 7: S3 모듈 (원본 아카이브 버킷) (AC: #6)

- [x] 7.1 자체 정의 (모듈 미사용 — 명시적 정의가 학생 계정 SCP 검증에 유리)
- [x] 7.2 `tracker-archive-${env}-${random_id.suffix.hex}` (4-byte hex)
- [x] 7.3 `aws_s3_bucket_public_access_block` 4종 모두 true
- [x] 7.4 **PIVOT — `aws:kms` → `AES256` (SSE-S3 폴백)**. KMS CMK 생성 권한 부족 가정
- [x] 7.5 `aws_s3_bucket_versioning` enabled
- [x] 7.6 lifecycle — 90일 IA, 365일 expiration, 비최신 30일, 멀티파트 7일
- [x] 7.7 bucket policy — Crawler Role PutObject/PutObjectAcl/AbortMultipartUpload + ListBucket Allow, 비-TLS 전체 Deny
- [x] 7.8 bootstrap 버킷도 동일하게 SSE-S3로 변경

### Task 8: 보안 baseline — PIVOT으로 모듈 비활성 (AC: #9, #11, #19)

- [ ] 8.1 `aws_ebs_encryption_by_default` — **PIVOT 비활성**. 학교 region default 정책에 의존 (deferred-work)
- [ ] 8.2 `aws_ebs_default_kms_key` — **PIVOT 비활성**. region default `alias/aws/ebs` 자동
- [ ] 8.3 `aws_cloudtrail` — **PIVOT 비활성**. 학교 organization trail 의존 (deferred-work)
- [ ] 8.4 CloudTrail destination 버킷 — **PIVOT 비활성**
- [ ] 8.5 `aws_budgets_budget` — **PIVOT 비활성**. 학교 사전 설정 budget 활용
- [x] 8.6 모듈은 placeholder만 유지(인터페이스 안정성). README에 PIVOT 사유 + production 복구 절차 명시

### Task 9: 시크릿 관리 (Secrets Manager) (AC: #15)

- [x] 9.1 `infra/terraform/modules/secrets/main.tf` 작성
- [x] 9.2 `tracker/{env}/{varco-api-key, rds-admin-password, proxy-credentials}` 3종
- [x] 9.3 placeholder만 정의 — varco/proxy는 ops 1회 주입, rds는 RDS 모듈이 random_password 자동 주입
- [x] 9.4 IAM 모듈에서 `detection_secret_arns` / `api_secret_arns` output 받아 ARN 한정 GetSecretValue 정책
- [x] 9.5 **PIVOT — `kms_key_id = null`로 AWS-managed `alias/aws/secretsmanager` 자동 사용** (KMS CMK 생성 권한 부족 가정)

### Task 10: 환경 합성 (`environments/dev/`, `environments/prod/`) (AC: #13)

- [x] 10.1 `environments/dev/main.tf` — **PIVOT** networking(default VPC lookup) + security_groups + secrets + s3_archive + iam + rds(t3.micro publicly_accessible=true) + ec2 ×3(모두 t3.medium x86_64). security_baseline 모듈 호출 X
- [x] 10.2 `environments/dev/backend.tf` — `tracker-tfstate-dev` + `use_lockfile = true`
- [x] 10.3 `environments/dev/variables.tf` + `providers.tf` + `terraform.tfvars.example`. PII placeholder
- [x] 10.4 `environments/prod/` — **PIVOT 미사용** (학생 계정 1개로 prod 분리 의미 없음). prod README + main.tf 헤더에 미사용 명시. CI workflow의 apply-prod 잡 비활성화(`if: false`)
- [ ] 10.5 `terraform validate` + `plan` 검증 — **별도 ops 세션으로 deferred** (사용자가 CloudShell 또는 IAM Access Key + MFA로 검증)
- [ ] 10.6 dev 실 apply + SSM 접속 + RDS 5432 차단 검증 — **별도 ops 세션으로 deferred**

### Task 11: pre-commit + GitHub Actions CI 게이트 (AC: #16, #17)

- [x] 11.1 `.pre-commit-config.yaml` — `antonbabenko/pre-commit-terraform` v1.105.0 + `pre-commit-hooks` v6.0.0
- [x] 11.2 `.tflint.hcl` — AWS plugin 0.47.0
- [x] 11.3 `.checkov.yml` — **PIVOT으로 skip 룰 확장** (CKV_AWS_88 NAT / CKV_AWS_157 Multi-AZ / CKV_AWS_17 publicly_accessible 학생 강제 / CKV_AWS_137·CKV2_AWS_67 AWS Config 미도입 / CKV2_AWS_61 tfstate lifecycle 부적합 / CKV_AWS_111 GHA 와일드카드 / CKV2_AWS_11 Flow Logs 미생성 / CKV_AWS_19 SSE-S3 폴백 / CKV_AWS_158·CKV_AWS_67 KMS CMK 미생성)
- [x] 11.4 `.github/workflows/terraform.yml` — paths 필터 + 4잡 구조
- [x] 11.5 static-checks → plan-dev → apply-dev / apply-prod (PIVOT으로 비활성)
- [x] 11.6 PR 코멘트 — `actions/github-script@v8`
- [x] 11.7 OIDC assume — `aws-actions/configure-aws-credentials@v6` + Fork PR 차단 if + workflow permissions 잡별 분리
- [x] 11.8 dev 자동 apply / **PIVOT — prod 잡 `if: false` 영구 비활성** (학생 계정 prod 미사용)

### Task 12: 모듈 README 자동화 + 사용 가이드 (AC: #16, #22)

- [x] 12.1 `infra/terraform/README.md` — **PIVOT 헤더 + 학생 계정 PIVOT 표** + 디렉토리 구조 + bootstrap 절차 + dev apply + Public repo 보안 가드 표 + drift 점검
- [x] 12.2 각 모듈 README placeholder + `<!-- BEGIN_TF_DOCS --> ... <!-- END_TF_DOCS -->` 영역 박힘
- [x] 12.3 `infra/DATA_POLICY.md` 작성 (NFR9)
- [x] 12.4 **PIVOT 추가** — `environments/prod/README.md` 학생 계정 미사용 사유 + production 복구 절차

### Task 13: 비용 검증 + 마무리 (AC: #19)

- [ ] 13.1 dev 환경 apply 후 비용 측정 — **별도 ops 세션으로 deferred** (사용자가 CloudShell 또는 IAM Access Key + MFA로 검증)
- [ ] 13.2 학교 사전 설정 budget 한도 확인 + Cost Explorer 추정
- [x] 13.3 region ap-northeast-2(Seoul) 확정
- [ ] 13.4 SSM Session Manager로 3개 EC2 접속 검증 — **별도 ops 세션**
- [ ] 13.5 RDS SG 검증 — laptop에서 5432 직접 접근 timeout 확인 + EC2에서 성공 확인 — **별도 ops 세션**
- [x] 13.6 sprint-status.yaml `5-3-aws-프로덕션-인프라-프로비저닝` 상태 `review`로 업데이트
- [ ] 13.7 PR 본문 — 24개 AC 매핑 + plan 결과 + Checkov 통과 — **PR 작성 시 처리**

## Dev Notes

### 🔴 PIVOT 2026-05-04 — 학생 계정 제약 적용 (A2 트랙)

본 스토리는 1차 작성 후 학생 계정 SCP 제약이 발견되어 architecture 전면 재설계됨.

#### PIVOT 사유 (콘솔에서 직접 확인된 제약)

| 영역 | 학생 계정 SCP 제약 | 본 스토리 영향 |
|---|---|---|
| **EC2 인스턴스 타입** | `t3.{nano, micro, small, medium}` 4종만 launch 가능 (콘솔 드롭다운 확정 2026-05-04) | r6g/t4g(arm64) → t3.medium x86_64로 전면 변경 |
| **RDS 엔진** | MySQL, PostgreSQL만 | postgres 그대로 OK |
| **RDS 템플릿** | "샌드박스" 강제 | Multi-AZ 자동 비활성, 우리 코드와 일치 |
| **RDS VPC** | Default VPC만 표시 | Custom VPC 미사용 → Default VPC data source lookup |
| **RDS publicly_accessible** | `true` 강제 | NFR7 위반. SG inbound source 한정 + `rds.force_ssl=1`로 보안 보강 |
| **RDS 컴퓨팅 연결** | "EC2 자동 연결 안 함" 강제 | 별도 SG 정의 패턴이라 OK |
| **루트 계정** | 학교 관리자만 보유 | 사용자는 IAM 사용자만 |
| **IAM 사용자 정책** | `<iam-advanced-policy>` + `<iam-basic-policy>` + `<power-user-policy>` + `<mfa-required-scp>` 등 | IAM Role/Policy/OIDC Provider 생성 가능 가정. **MFA 필수** |
| **AWS Config / SecurityHub / GuardDuty** | 학생 계정 권한 부족 가정 | 기존 결정과 일치 (제외) |
| **CloudTrail / KMS CMK / Budgets / VPC Flow Logs** | 학생 계정 권한 부족 가정 (보수적) | 모두 코드 비활성. 학교 default 정책 의존 |

#### 새 architecture decision (PIVOT 후)

| 항목 | PIVOT 이전 | PIVOT 후 |
|---|---|---|
| EC2 | crawler r6g.large(16GB) / detection t4g.medium(4GB) / api t4g.large(8GB), 모두 arm64 | **모두 t3.medium x86_64 (4GB ×3)** |
| AMI | Amazon Linux 2023 arm64 | **Amazon Linux 2023 x86_64** |
| VPC | Custom VPC `10.20.0.0/16` + subnet 4개 + S3 endpoint + Flow Logs | **Default VPC data source lookup만** |
| Subnet | public 2 + private 2 | **Default VPC subnet 11개 활용** (모두 public, AZ 분산) |
| RDS | db.t4g.micro, publicly_accessible=false, private subnet 배치, custom subnet group | **db.t3.micro, publicly_accessible=true(강제), default subnet group, parameter group `rds.force_ssl=1`** |
| S3 SSE | `aws:kms` (region default key) + bucket key | **`AES256` (SSE-S3)** |
| CloudTrail | multi-region + KMS CMK + 90일 보관 + 별도 trail S3 버킷 | **미생성** (학교 organization trail 의존) |
| KMS CMK | CloudTrail 전용 CMK (rotation enabled) | **미생성** (모든 SSE는 region default 또는 SSE-S3) |
| AWS Budgets | $215/MONTHLY + 80%/100%/forecast 알림 | **미생성** (학교 사전 설정 budget 활용) |
| EBS encryption | `aws_ebs_encryption_by_default` 활성화 | **region default 정책 의존** (학교가 켰을 가능성) |
| VPC Flow Logs | CloudWatch Logs 14일 | **미생성** (Default VPC에 권한 부족 가능성) |
| 환경 분리 | dev + prod 양쪽 활성 | **dev 1개만 활성, prod portfolio 코드로만 보존** |
| 인스턴스 메모리 합 | 16+4+8 = 28GB | **4+4+4 = 12GB** (Crawler RAM 우선 메모리 결정 미충족 — deferred) |

#### Crawler RAM 다운그레이드 영향 (deferred-work)

기존 결정: Playwright/Nodriver Chromium + FlareSolverr 동시 실행으로 8~16GB 필요 (`memory/project_crawler_ram_priority.md`).
PIVOT 후: t3.medium 4GB만 가용. 다음 운영 패턴 중 택1을 Story 5.4 부하 측정에서 결정:
1. Chromium 단일 인스턴스 + FlareSolverr 별도 EC2(또는 컨테이너) 분리
2. swap 4GB 추가로 OOM 회피 (디스크 IO 비용)
3. 헤드리스 Chromium 옵션 최적화(`--single-process` 등)로 메모리 압축
4. APScheduler 동시 실행 worker를 1로 강제

#### IAM 사용자 + MFA + Access Key 운영 절차

학생 IAM 사용자(`<mfa-required-scp>` 정책) 운영 시 인증 패턴:
- **AWS CloudShell** (권장) — 콘솔 MFA 로그인 후 CloudShell 진입 시 자동 인증, 별도 토큰 불필요
- **로컬 + AWS CLI** — `aws sts get-session-token --serial-number arn:aws:iam::<AWS_ACCOUNT_ID>:mfa/<MFA-device> --token-code 123456 --duration-seconds 43200` → `AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN` 환경변수 export → terraform apply
- **GitHub Actions OIDC** — IAM OIDC Provider 생성 가능하면 그대로. MFA는 OIDC와 별도 path

### 본 스토리 범위 (Scope Boundary — 가장 중요)

| 이번 스토리에서 한다 | 이번 스토리에서 **하지 않는다** |
|---|---|
| `infra/terraform/` 전체 모듈·환경 코드 작성 | Prometheus/Grafana 메트릭 수집 (Story 5.1) |
| dev 환경 실제 apply (검증용) | 통합 CI/CD 배포 자동화 — Spring/React 코드 EC2 배포 (Story 5.2) |
| GitHub OIDC + Terraform CI 워크플로우 | application 코드 빌드/배포 워크플로우 (Story 5.2) |
| EBS/CloudTrail/Budgets 보안 baseline | AWS Config / SecurityHub / GuardDuty (architecture.md:252 학생 예산 외) |
| Secrets Manager 시크릿 placeholder 생성 | 실제 시크릿 값 주입(Console 또는 ops 스크립트, 1회성) |
| `infra/DATA_POLICY.md` + `infra/terraform/README.md` | `docs/quality-gate-final.md` (Story 5.4) |
| dev 환경 24시간 비용 검증 | prod 환경 실제 apply (수동 승인 게이트로 보호) |

### 선행 결정 사항 — PR #18 ([commit bd172d9](https://github.com/byungju0/261RCOSE45700/commit/bd172d9))

PR #18에서 architecture.md / epics.md / 기획서.md 3개 문서에 일관 반영. 본 스토리는 그 결정을 코드로 옮긴다.

| 결정 항목 | 값 | 출처 |
|---|---|---|
| Terraform 버전 핀 | `>= 1.14, < 2.0` | architecture.md:237 |
| AWS provider 핀 | `~> 6.0` (실 6.43.x) | architecture.md:238 |
| terraform-aws-modules 핀 | vpc 6.6 / rds 7.2 / ec2-instance 6.4 / security-group 5.3 | architecture.md:239 |
| state 백엔드 | S3 + native locking (`use_lockfile = true`) | architecture.md:230 |
| 환경 분리 | 디렉토리 분리 (`environments/dev,prod/`) | architecture.md:231 |
| 모듈 사용 | terraform-aws-modules 공식 우선 | architecture.md:232 |
| GitHub Actions ↔ AWS | OIDC + IAM Role | architecture.md:233 |
| CI 게이트 | fmt + validate + TFLint + Checkov | architecture.md:234 |
| pre-commit | antonbabenko/pre-commit-terraform | architecture.md:253 |
| Crawler EC2 | r6g.large 2vCPU/16GB arm64 ~$73.6/월 | architecture.md:241 |
| Detection EC2 | t4g.medium 2vCPU/4GB arm64 ~$24.5/월 | architecture.md:242 |
| API EC2 | t4g.large 2vCPU/8GB arm64 ~$49.0/월 | architecture.md:243 |
| RDS | PostgreSQL 16.13 db.t4g.micro Single-AZ backup 7일 ~$11.5/월 | architecture.md:245-246 |
| EC2 접근 | SSM Session Manager 단독 (외부 22번 차단) | architecture.md:247 |
| S3 트래픽 | VPC Gateway Endpoint (무료, NAT 회피) | architecture.md:248 |
| 보안 baseline | EBS encryption + VPC Flow Logs + CloudTrail KMS | architecture.md:249-251 |
| 미도입 | AWS Config / SecurityHub / GuardDuty (Checkov로 대체) | architecture.md:252 |
| 월 예산 상한 | 30만원 (~$215, 환율 1400원/USD) | architecture.md:240 |

### 보류된 결정 — SPIKE 5.0 추가 항목

본 스토리 진입 직전 PM/팀과 합의 필요. 결정 즉시 architecture.md에 backport.

1. **NAT 운영 방식 (SPIKE 5.0 #11)** — Gateway / Instance / public-only 중 택 1
   - Gateway: $37/월, HA 자동, 운영 부담 0
   - Instance(t4g.nano): ~$3/월, SPOF, 직접 운영 필요
   - public-only: NAT 자체 없음 — NFR7(VPC 내부망 접근) 정합 검토 필수
   - **본 스토리 영향:** Task 2.2 networking 모듈 변수 분기. 비용 합계 변동.
2. **EC2 접근 백업 방식 (SPIKE 5.0 #12)** — SSM Session Manager 단독 한계 발견 시
   - **본 스토리 가정:** SSM 단독으로 구현. 한계 식별 시 deferred-work에 기록 후 후속 처리.

### 기존 코드 현황 (재사용 / 수정 금지)

**이미 존재하는 인프라 관련 파일:**

| 파일 | 상태 | 주의사항 |
|---|---|---|
| `infra/docker-compose.yml` | Story 1.3 done | 로컬 개발 환경 — 수정 금지 |
| `infra/docker-compose.dev.yml`, `prod.yml` | Story 1.3 done | 환경 오버라이드 — 수정 금지 |
| `infra/prometheus/`, `infra/grafana/` | Story 5.1 범위 | 본 스토리에서 생성하지 않음 |
| `.github/workflows/{crawler,detection,api,dashboard}.yml` | Story 1.5 done | 수정 금지 — `terraform.yml` 신규 추가만 |
| `docs/ci-setup.md` | Story 1.5 | path-filtered + aggregator 전략 문서. Story 5.2 strict CI 합류 시 갱신 |

### 디렉토리 구조 (architecture.md:669-685 명시)

```
infra/terraform/
├── bootstrap/                  # 1회성 state 백엔드 생성
│   ├── main.tf                 # S3 버킷 + 암호화 + 버전관리 + native locking
│   ├── variables.tf
│   └── README.md
├── modules/                    # 재사용 모듈
│   ├── networking/             # VPC + 서브넷 + NAT (결정 보류) + S3 Endpoint + Flow Logs
│   ├── security-groups/        # crawler/detection/api/rds 4종 SG
│   ├── iam/                    # EC2 Instance Role + GitHub OIDC
│   ├── ec2-service/            # crawler/detection/api 공통 패턴
│   ├── rds/                    # PostgreSQL 16.13 Single-AZ
│   ├── s3-archive/             # 원본 아카이브 버킷
│   └── secrets/                # Secrets Manager placeholder
└── environments/
    ├── dev/
    │   ├── main.tf             # modules 호출
    │   ├── variables.tf
    │   ├── terraform.tfvars    # .gitignore (시크릿 변수 0건 검증)
    │   └── backend.tf          # tracker-tfstate-dev S3 + native locking
    └── prod/
        └── (동일 구조, prod tfstate)
```

> architecture.md 원안의 `modules/elasticache/`와 `modules/s3-frontend/`는 **본 스토리 범위 외**. Redis는 architecture.md:243에 따라 API EC2 docker-compose로 동거하며 ElastiCache 미사용. Dashboard 호스팅은 SPIKE 5.0 #2 결정값 따라 별도 처리.

### Terraform 버전 핀 — 검증 메모

PR #18 commit message ([bd172d9](https://github.com/byungju0/261RCOSE45700/commit/bd172d9))에서 "모든 모듈 버전은 GitHub Releases API로 직접 조회하여 확정" 명시. 2026-04-30 기준:

```hcl
terraform {
  required_version = ">= 1.14, < 2.0"   # 1.15.0 stable, S3 native locking 1.10+
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"                 # 6.43.x, 2025-06-18 GA
    }
  }
}

# environments/dev/main.tf
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.6"                     # 6.6.1
}
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 7.2"                     # 7.2.0 (v7 메이저 — v3로 잘못 핀 금지)
}
module "ec2_instance" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.4"                     # 6.4.0
}
module "security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.3"                     # 5.3.1
}
```

### Checkov 기대 통과 룰 + skip 룰 (PR 단계 자동 차단)

**통과:**

| 룰 ID | 의미 | 본 스토리 충족 방식 |
|---|---|---|
| `CKV_AWS_3` | EBS 볼륨 KMS 암호화 | Task 8.1 region default + Task 5.4 모듈 입력 명시 |
| `CKV_AWS_35` | CloudTrail KMS 암호화 | Task 8.3 `kms_key_id` 지정 |
| `CKV_AWS_24` | SG inbound 22 0.0.0.0/0 차단 | Task 3 모든 SG에서 22 inbound 미정의 |
| `CKV_AWS_25` | SG inbound 3389 차단 | 동일 |
| `CKV_AWS_79` | EC2 IMDSv2 강제 | Task 5.7 `http_tokens = "required"` |
| `CKV_AWS_111` | IAM 정책 와일드카드 Resource 금지 | Task 4 모든 정책 ARN 명시 |
| `CKV_AWS_18` | S3 access logging | Task 7 또는 8.4 CloudTrail S3 access logging |
| `CKV_AWS_53,54,55,56` | S3 퍼블릭 차단 4종 | Task 7.3 `block_public_*` 4종 true |
| `CKV_AWS_157` | RDS Multi-AZ | **skip** — architecture.md:245 학생 예산 결정 (Single-AZ + backup 7일) |

**Skip(`.checkov.yml`에 사유 주석 명시):**

| 룰 ID | 의미 | Skip 사유 |
|---|---|---|
| `CKV_AWS_88` | EC2 퍼블릭 IP 비할당 | **NAT 없음(public subnet only) 결정으로 EC2가 public IP 보유**. 인바운드는 보안 그룹 4종 모두 0으로 차단되어 외부 노출 risk 차단(SSM Session Manager outbound로 운영자 접근). SPIKE 5.0 #11 + Story 5-3 AC #23 결정 근거 인용. 향후 `nat_strategy = "instance"|"gateway"` 변경 시 본 skip 자동 해제 가능 |
| `CKV_AWS_157` | RDS Multi-AZ 활성 | architecture.md:245 학생 예산(30만원) 상한 결정 — Single-AZ + automated backup 7일로 데이터 손실 위험 완화 |

### 비용 추정 (architecture.md:240 미국 region 기준)

| 리소스 | 사양 | 월 비용 |
|---|---|---|
| Crawler EC2 | r6g.large | $73.6 |
| Detection EC2 | t4g.medium | $24.5 |
| API EC2 | t4g.large | $49.0 |
| RDS | db.t4g.micro Single-AZ + backup 7일 | $11.5 |
| EBS gp3 (3 EC2) | ~30GB ×3 | ~$7.2 |
| S3 (archive + cloudtrail + tfstate) | 100GB + 요청 | ~$5 |
| VPC Flow Logs CloudWatch | 14일 | ~$1.5 |
| CloudTrail | 모든 region, KMS | ~$2 (관리 이벤트 무료, 데이터 이벤트 사용 안 함) |
| **NAT** | **없음 (public subnet only)** | **$0** |
| **합계** | | **~$174/월** |

ap-northeast-2 채택 시 5~15% 가산 → 약 $183~$200. **$215 예산 상한 내 여유 ~$15~$32 확보** — BERT 도입 시(c6g.large +$60) 예산 협의 필요하나 NAT 없음으로 가장 큰 비용 변수 제거.

향후 NAT 도입 시 비용 영향:
- `nat_strategy = "instance"` (fck-nat t4g.nano): +$3.5/월
- `nat_strategy = "gateway"` (NAT Gateway): +$35/월

### 회귀 위험 / 안티패턴

- **ClickOps 금지:** Console에서 한 번 만든 리소스를 Terraform import하지 않은 채 두면 영원히 drift. 모든 리소스는 코드 → apply가 단일 진실의 원천.
- **DynamoDB lock 테이블 만들지 말 것:** Terraform 1.10+ S3 native locking 사용 (architecture.md:230). 잘못 만들면 운영 부담만 늘어남.
- **tfstate에 평문 시크릿 넣지 말 것 (NFR5):** `aws_secretsmanager_secret_version`의 `secret_string`을 Terraform 변수로 주입하면 state에 평문 저장됨. placeholder만 정의 + Console/ops 스크립트로 1회 주입 패턴 사용 (Task 9.3).
- **Resource: "*" 와일드카드 금지:** Checkov `CKV_AWS_111` 차단. 모든 IAM 정책에 ARN 명시.
- **0.0.0.0/0 inbound 22 금지:** SSH 키 안 쓰고 SSM 단독이므로 이 포트는 모든 SG에서 미정의로 유지.
- **AMI x86_64 잘못 선택 금지:** Graviton 인스턴스에 x86_64 AMI 부팅 시도 시 즉시 실패. `data "aws_ami"` 필터에 `architecture = "arm64"` 명시 필수.
- **모듈 v3 핀 금지 (RDS):** `terraform-aws-modules/rds/aws`는 v7 메이저로 진입한 지 오래. v3로 잘못 핀하면 EOL 모듈 사용 (architecture.md:239 명시 경고).
- **`terraform apply -auto-approve` 직접 실행 금지:** dev는 main 머지 시 GitHub Actions가, prod는 환경 보호 규칙 + 수동 승인으로만 apply.

### 테스트 표준

본 스토리는 인프라 코드라 단위 테스트 대신 **정적 분석 + plan 검증 + 실 apply**가 게이트:

1. `terraform fmt -check` (CI)
2. `terraform validate` (CI)
3. TFLint AWS 룰셋 (CI)
4. Checkov 보안 스캔 (CI, 1건 실패 시 차단)
5. `terraform plan` PR 코멘트 (사람 리뷰)
6. dev 환경 실 apply 후 검증 체크리스트 (Task 13.4~13.5)
7. SSM 접속 / RDS 격리 / S3 퍼블릭 차단 / Budgets 알림 동작 수동 확인

### 환경별 차이 요약

| 항목 | dev | prod |
|---|---|---|
| state 버킷 | tracker-tfstate-dev | tracker-tfstate-prod |
| RDS deletion_protection | false | true |
| RDS skip_final_snapshot | true | false |
| Multi-AZ | false | false (학생 예산) |
| AWS Budgets 알림 수신 | dev 담당자 이메일 | dev + PM 이메일 |
| apply 트리거 | main 머지 자동 | GitHub Environments 수동 승인 |

### Project Structure Notes

- 본 스토리 산출물은 `infra/terraform/**` 신규 추가. 기존 `infra/` 트리(docker-compose, prometheus, grafana)는 그대로 보존.
- `.github/workflows/terraform.yml` 신규 추가 — 기존 4종 워크플로우(`crawler.yml`, `detection.yml`, `api.yml`, `dashboard.yml`) 수정 없음.
- `docs/` 변경 없음. `infra/DATA_POLICY.md` + `infra/terraform/README.md`만 신규.

### References

- [architecture.md#Infrastructure & Deployment](_bmad-output/planning-artifacts/architecture.md#L221-L256) — Terraform/AWS 22개 결정
- [architecture.md#Project Structure](_bmad-output/planning-artifacts/architecture.md#L669-L685) — `infra/terraform/` 디렉토리 합의
- [epics.md#Epic 5 SPIKE 5.0](_bmad-output/planning-artifacts/epics.md#L638-L669) — 12개 SPIKE 결정 항목
- [epics.md#Story 5.3](_bmad-output/planning-artifacts/epics.md#L702-L734) — Story AC 원본
- [PR #18 (commit bd172d9)](https://github.com/byungju0/261RCOSE45700/commit/bd172d9) — Terraform IaC 정책 + AWS 사이징 결정
- [docs/ci-setup.md](docs/ci-setup.md) — Story 1.5 CI 운영 가이드 (Story 5.2 strict 합류 예정)
- [Story 1.4](_bmad-output/implementation-artifacts/1-4-flyway-db-초기-스키마-및-varco-mock-서버-구축.md) — RDS PostgreSQL 스키마 (Flyway V1~V3) — RDS 인스턴스 프로비저닝 후 마이그레이션 실행
- [memory/project_aws_budget.md](.claude/projects/-Users-jmac-Desktop-261RCOSE45700/memory/project_aws_budget.md) — 30만원 예산 상한 근거
- [memory/project_crawler_ram_priority.md](.claude/projects/-Users-jmac-Desktop-261RCOSE45700/memory/project_crawler_ram_priority.md) — Crawler r6g.large RAM 우선 결정 근거

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Claude Opus 4.7)

### Debug Log References

- 2026-05-04 1차 작성: 24개 AC + 13 task 코드 측면 모두 충족 (Option A: 코드/CI/문서까지, 실 apply는 별도 ops 세션 deferred)
- 2026-05-04 보안 강화: terraform.yml fork PR 차단 + variables.tf PII default 제거 + 버전 갱신 9건 + OIDC thumbprint 정정 + README rulesets 갱신 + CODEOWNERS + Dependabot + workflow permissions 잡별 분리
- 2026-05-04 PIVOT: 학생 계정 SCP 제약 발견 후 architecture 전면 재설계 (A2 트랙)
  - EC2 콘솔 확인: t3.{nano,micro,small,medium} 4종만 가능 → r6g/t4g 폐기, t3.medium ×3 채택
  - RDS 콘솔 확인: MySQL/PostgreSQL만, 샌드박스 템플릿 강제, Default VPC 강제, publicly_accessible 강제, EC2 자동 연결 X
  - IAM 정책 확인: <iam-advanced-policy> + <iam-basic-policy> + <power-user-policy> + <mfa-required-scp> — IAM Role 생성 가능 가정 (apply 시 검증 필요)
  - 보수적 가정: CloudTrail/KMS CMK/Budgets/VPC Flow Logs는 학생 계정 권한 부족으로 코드 비활성

### Completion Notes List

#### 1차 작성 (PIVOT 이전, production-grade IaC)

- ✅ Bootstrap (S3 tfstate + native locking, DynamoDB X)
- ✅ 8개 모듈 작성 (networking + security-groups + iam + ec2-service + rds + s3-archive + secrets + security-baseline)
- ✅ environments dev + prod 양쪽 구성
- ✅ pre-commit + GitHub Actions terraform.yml CI 4잡 구조 (static-checks + plan-dev + apply-dev + apply-prod)
- ✅ 보안 가드 9종 적용 (시크릿 코드 0건, OIDC, Checkov skip 사유 명시, fork PR 차단 등)

#### 2차 강화 (보안 + 버전 갱신)

- ✅ Workflow permissions 잡별 분리 (Principle of Least Privilege)
- ✅ Fork PR plan-dev 차단 if 추가 (pwn-request 패턴 회피)
- ✅ PII(이메일) variables.tf default 제거 + GitHub Variables 주입 패턴
- ✅ 버전 갱신 9건: pre-commit-terraform v1.96.1→v1.105.0, pre-commit-hooks v5→v6, TFLint AWS plugin 0.36.0→0.47.0, TF CLI 1.15.0→1.15.1, setup-terraform v3→v4, configure-aws-credentials v4→v6, setup-tflint v4+v0.55.1→v6+v0.62.0, checkout v4→v6, github-script v7→v8
- ✅ OIDC thumbprint 정정 (AWS provider v6 + GitHub IdP는 retained but not used)
- ✅ README "Branch Protection" → "Repository Rulesets"(2026 표준)
- ✅ `.github/CODEOWNERS` 신규 — `infra/terraform/**` / `.github/` / `dashboard/` 변경 시 `@gitjay3` 자동 review
- ✅ `.github/dependabot.yml` 신규 — terraform/github-actions/npm 매주 자동 PR

#### 3차 PIVOT (학생 계정 SCP 적용)

- ✅ `modules/networking/` — custom VPC 생성 → Default VPC data source lookup (자원 미생성)
- ✅ `modules/ec2-service/` — AMI x86_64 강제, instance_type validation = t3.{nano,micro,small,medium} 4종 한정
- ✅ `modules/rds/` — db.t3.micro + publicly_accessible=true(강제) + default subnet group + parameter group `rds.force_ssl=1` 보안 보강
- ✅ `modules/s3-archive/` + `bootstrap/` — SSE-KMS → SSE-S3(AES256) 폴백
- ✅ `modules/security-baseline/` — CloudTrail/KMS CMK/Budgets/EBS encryption by default 모두 비활성 (placeholder만)
- ✅ `modules/secrets/` — KMS는 AWS-managed `alias/aws/secretsmanager` 자동 사용
- ✅ `modules/iam/` — GHA Terraform Role의 cloudtrail/kms/budgets 액션 제거
- ✅ `environments/dev/` — networking/iam/secrets/s3_archive/rds/ec2 ×3 호출. security-baseline 호출 제거
- ✅ `environments/prod/` — 학생 계정 미사용 헤더 + README + CI workflow apply-prod `if: false` 비활성
- ✅ `.checkov.yml` skip 룰 확장 — CKV_AWS_17 (publicly_accessible 학생 강제) + CKV2_AWS_11 (Flow Logs 미생성) + CKV_AWS_19 (SSE-S3 폴백) + CKV_AWS_158/CKV_AWS_67 (KMS CMK 미생성) + CKV2_AWS_61 (tfstate lifecycle 부적합) 추가
- ✅ README.md 갱신 — PIVOT 헤더 + 본래 vs PIVOT 결정 비교표 + Public repo 보안 가드 + ops 체크리스트
- ✅ AC 24개 갱신 — #3 (인스턴스 t3.medium x86_64), #4 (publicly_accessible=true 강제 + 보안 보강), #6 (S3 endpoint 제외), #9-#11 (CloudTrail/KMS/Flow Logs 비활성), #14 (vpc/aws 모듈 미사용), #19 (Budgets 비활성 + 학교 budget 활용), #23 (Default VPC), #24 (publicly_accessible=true + SG/TLS 보강) 등
- ✅ deferred-work 13항목 추가 (Crawler RAM 다운그레이드, EBS encryption 검증, Flow Logs 보강, CloudTrail 학교 trail 의존, MFA 운영, prod 환경 미사용, architecture.md backport 등)

#### 본 세션 deferred (별도 ops 또는 향후 sprint)

- ⏸ Bootstrap 1회 apply (CloudShell 또는 IAM + MFA로 사용자 직접)
- ⏸ dev environment apply + SSM 접속 검증 + RDS 5432 차단 검증
- ⏸ AWS Cost Explorer로 24h 비용 측정
- ⏸ GitHub Repository Variables 등록 (AWS_TF_ROLE_DEV, OIDC_PROVIDER_ARN, BUDGET_ALERT_EMAILS — 단 BUDGET은 학교 활용으로 미사용)
- ⏸ GitHub Settings → Code security / Actions / Rulesets 1회 점검
- ⏸ Secrets Manager 1회 주입 (varco_api_key, proxy_credentials)
- ⏸ architecture.md / epics.md / 기획서.md PIVOT backport (PM/팀 합의)

### File List

#### 신규 (PIVOT 이전 + PIVOT 후 모두 동일 경로)

- `infra/terraform/bootstrap/main.tf`
- `infra/terraform/bootstrap/variables.tf`
- `infra/terraform/bootstrap/outputs.tf`
- `infra/terraform/bootstrap/README.md`
- `infra/terraform/modules/networking/main.tf` (PIVOT으로 data source 기반 재작성)
- `infra/terraform/modules/networking/variables.tf` (PIVOT으로 단순화)
- `infra/terraform/modules/networking/outputs.tf` (PIVOT으로 first/second_subnet_id 노출)
- `infra/terraform/modules/networking/README.md` (PIVOT 사유 명시)
- `infra/terraform/modules/security-groups/main.tf`
- `infra/terraform/modules/security-groups/variables.tf`
- `infra/terraform/modules/security-groups/outputs.tf`
- `infra/terraform/modules/security-groups/README.md`
- `infra/terraform/modules/iam/main.tf` (PIVOT으로 GHA Role의 CloudTrail/KMS/Budgets 권한 제거)
- `infra/terraform/modules/iam/variables.tf`
- `infra/terraform/modules/iam/outputs.tf`
- `infra/terraform/modules/iam/README.md`
- `infra/terraform/modules/ec2-service/main.tf` (PIVOT으로 x86_64 AMI)
- `infra/terraform/modules/ec2-service/variables.tf` (PIVOT으로 instance_type validation t3.* 4종)
- `infra/terraform/modules/ec2-service/outputs.tf`
- `infra/terraform/modules/ec2-service/README.md` (PIVOT 사유 명시)
- `infra/terraform/modules/rds/main.tf` (PIVOT으로 publicly_accessible=true + force_ssl + default subnet group)
- `infra/terraform/modules/rds/variables.tf` (PIVOT으로 db.t3.* validation + db_subnet_group_name 변수)
- `infra/terraform/modules/rds/outputs.tf`
- `infra/terraform/modules/rds/README.md` (PIVOT 사유 + 보안 보강 패턴 명시)
- `infra/terraform/modules/s3-archive/main.tf` (PIVOT으로 SSE-S3)
- `infra/terraform/modules/s3-archive/variables.tf`
- `infra/terraform/modules/s3-archive/outputs.tf`
- `infra/terraform/modules/s3-archive/README.md`
- `infra/terraform/modules/security-baseline/main.tf` (PIVOT으로 placeholder만)
- `infra/terraform/modules/security-baseline/variables.tf` (PIVOT으로 단순화)
- `infra/terraform/modules/security-baseline/outputs.tf` (PIVOT으로 비활성)
- `infra/terraform/modules/security-baseline/README.md` (PIVOT 사유 + production 복구 절차)
- `infra/terraform/modules/secrets/main.tf` (PIVOT 주석 추가)
- `infra/terraform/modules/secrets/variables.tf`
- `infra/terraform/modules/secrets/outputs.tf`
- `infra/terraform/modules/secrets/README.md`
- `infra/terraform/environments/dev/main.tf` (PIVOT 적용)
- `infra/terraform/environments/dev/backend.tf`
- `infra/terraform/environments/dev/providers.tf`
- `infra/terraform/environments/dev/variables.tf` (PIVOT으로 PII default 제거)
- `infra/terraform/environments/dev/outputs.tf` (PIVOT으로 cloudtrail_bucket 제거)
- `infra/terraform/environments/dev/terraform.tfvars.example`
- `infra/terraform/environments/prod/main.tf` (PIVOT 미사용 헤더 추가)
- `infra/terraform/environments/prod/backend.tf`
- `infra/terraform/environments/prod/providers.tf`
- `infra/terraform/environments/prod/variables.tf`
- `infra/terraform/environments/prod/outputs.tf`
- `infra/terraform/environments/prod/terraform.tfvars.example`
- `infra/terraform/environments/prod/README.md` (PIVOT 미사용 사유 + 복구 절차)
- `infra/terraform/README.md` (PIVOT 헤더 + 본래 vs PIVOT 결정 비교 + Public repo 보안 가드)
- `infra/DATA_POLICY.md`
- `.pre-commit-config.yaml`
- `.tflint.hcl`
- `.checkov.yml` (PIVOT으로 skip 룰 확장)
- `.terraform-docs.yml`
- `.github/workflows/terraform.yml` (PIVOT으로 apply-prod `if: false` 비활성)
- `.github/CODEOWNERS`
- `.github/dependabot.yml`

#### 수정

- `.gitignore` — Terraform 패턴 추가 (`*.tfstate`, `terraform.tfvars` 등)

#### 갱신

- `_bmad-output/implementation-artifacts/sprint-status.yaml` (Story 5-3 in-progress → review)
- `_bmad-output/implementation-artifacts/deferred-work.md` (Story 5-3 deferred 28항목)
- `_bmad-output/implementation-artifacts/5-3-aws-프로덕션-인프라-프로비저닝.md` (본 파일)

### Change Log

| 날짜 | 변경 |
|---|---|
| 2026-05-04 | 1차 작성 — production-grade IaC 코드 + CI + 문서 (Option A: 실 apply 제외) |
| 2026-05-04 | 2차 강화 — 보안 가드 + 버전 갱신 9건 + CODEOWNERS + Dependabot + workflow permissions 잡별 분리 |
| 2026-05-04 | **PIVOT** — 학생 계정 SCP 제약 발견. architecture 전면 재설계 (A2 트랙). r6g/t4g → t3.medium x86_64, custom VPC → Default VPC, publicly_accessible=false → true(강제), CloudTrail/KMS CMK/Budgets/Flow Logs 코드 비활성, prod 환경 미사용 |
