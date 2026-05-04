# Bootstrap — Terraform State Backend

이 디렉토리는 **환경별 1회만** 적용되는 Terraform state 백엔드(S3 버킷)를 생성한다.
이후 `environments/dev/`, `environments/prod/`는 여기서 만든 버킷을 backend로 사용한다.

## 무엇을 만드나

| 리소스 | 비고 |
|---|---|
| `aws_s3_bucket.tfstate` (`tracker-tfstate-{env}`) | state 보관 |
| `aws_s3_bucket_versioning` | 활성 (실수 복구) |
| `aws_s3_bucket_server_side_encryption_configuration` | `aws:kms` (region default key) |
| `aws_s3_bucket_public_access_block` | 4종 모두 `true` |

> **DynamoDB lock 테이블은 만들지 않는다.** Terraform 1.10+ S3 native locking
> (`use_lockfile = true`)으로 대체. (architecture.md:230)

## 1회 apply 절차 — AWS CloudShell만 가능

학생 계정(account `<AWS_ACCOUNT_ID>`, IAM user `<IAM_USER>`)은:
- `<mfa-required-scp>` — MFA 인증 필수
- **IAM Access Key 발급 차단** (`iam:ListAccessKeys` 권한 거부 확인 2026-05-04)

따라서 로컬 머신 + `aws configure` 옵션 사용 불가. **AWS CloudShell**만 가능.

```bash
# 1. AWS 콘솔에 MFA로 로그인 (계정 ID: <AWS_ACCOUNT_ID>)
# 2. 우상단 CloudShell 아이콘 클릭 (Seoul region 선택 확인)
# 3. CloudShell에서:

sudo yum install -y unzip git
curl -O https://releases.hashicorp.com/terraform/1.15.1/terraform_1.15.1_linux_amd64.zip
unzip terraform_1.15.1_linux_amd64.zip
sudo mv terraform /usr/local/bin/

git clone https://github.com/byungju0/261RCOSE45700.git
cd 261RCOSE45700/infra/terraform/bootstrap

# dev만 apply (prod는 학생 계정 미사용)
terraform init
terraform apply -var "env=dev"
# → tracker-tfstate-dev S3 버킷 생성 (SSE-S3, versioning, 4종 차단)

# state 파일 백업 — 즉시 로컬 다운로드 권장
# CloudShell 우상단 Actions → Download file → terraform.tfstate
# CloudShell home은 1GB 한도 + 자동 wipe 가능 → 반드시 별도 백업
```

⚠️ prod 환경은 학생 계정 미사용 — `terraform apply -var "env=prod"` 실행 금지.

## state 파일 보관

bootstrap 자신의 state(`terraform.tfstate`)는 **로컬에 보관**한다. (이 디렉토리에서 만든 S3 버킷에 자기 state를 넣으면 닭이 먼저인지 달걀이 먼저인지 문제가 생긴다.)

- 로컬 백업 권장 (예: 1Password / Bitwarden Secure Note에 압축본)
- `.gitignore`에 `*.tfstate*` 포함되어 있는지 확인
- 별도 백엔드로 이전이 필요하면 `terraform state pull > backup.tfstate` 후 처리

## 주의 — 절대 destroy 금지

이 버킷은 dev/prod 환경 전체의 Terraform state를 보관한다. 삭제하면:
- 모든 환경의 state가 사라지고
- AWS 리소스는 그대로 남아 (관리 불가능한) drift 상태가 된다.

destroy가 필요하면:
1. dev/prod 환경에서 모든 리소스 `terraform destroy` 먼저
2. state가 비어 있는지 확인
3. 그 다음에야 bootstrap destroy

## 출력

| Output | 용도 |
|---|---|
| `tfstate_bucket_name` | environments/{env}/backend.tf의 `bucket = ...`에 입력 |
| `region` | environments/{env}/backend.tf의 `region = ...`에 입력 |
