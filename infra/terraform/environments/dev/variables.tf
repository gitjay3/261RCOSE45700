# 학생 계정 PIVOT — networking 모듈이 Default VPC data source만 사용하고
# security-baseline 모듈도 비활성이라 vpc_cidr / availability_zones /
# public_subnet_cidrs / private_subnet_cidrs / budget_alert_emails 변수
# 모두 미사용이 되어 제거. 본래 변수 정의는 git history에서 PIVOT 이전
# commit(`bd172d9` 또는 `ceb602c`)으로 복원 가능.

variable "region" {
  description = <<-EOT
    AWS region. Default: ap-northeast-2(Seoul).
    학생 계정 SCP `<region-restrict-policy>`가 us-east-1만 차단. 나머지 16개 region 허용.
    architecture decision은 ap-northeast-2 — 변경 시 비용/지연 영향 평가 필요.
  EOT
  type        = string
  default     = "ap-northeast-2"

  validation {
    # 학교 허용 region 16개 (us-east-1 차단)
    condition = contains(
      [
        "us-east-2", "us-west-1", "us-west-2",
        "ap-south-1", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
        "ap-southeast-1", "ap-southeast-2",
        "ca-central-1",
        "eu-central-1", "eu-west-1", "eu-west-2", "eu-west-3", "eu-north-1",
        "sa-east-1",
      ],
      var.region,
    )
    error_message = "학생 계정 제약: region이 학교 허용 화이트리스트에 없음. us-east-1(버지니아) 차단 + 나머지 16개 region만 허용 (<region-restrict-policy> 정책)."
  }
}

variable "name_prefix" {
  description = "리소스 prefix."
  type        = string
  default     = "tracker-dev"
}

variable "github_repository" {
  description = "GitHub OIDC trust 매칭에 사용할 repo (owner/name)."
  type        = string
  default     = "byungju0/261RCOSE45700"
}

variable "tfstate_bucket_name" {
  description = "Bootstrap이 만든 tfstate 버킷 이름 (GitHub Actions Role 권한 한정용)."
  type        = string
  default     = "tracker-tfstate-dev"
}
