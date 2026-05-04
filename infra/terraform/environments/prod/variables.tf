# 학생 계정 PIVOT — prod 환경 미사용. 본 파일은 모듈 호출 인터페이스 안정성용.
# 본래 production-grade 변수(vpc_cidr / availability_zones / public_subnet_cidrs /
# private_subnet_cidrs / budget_alert_emails 등)는 git history(`bd172d9` 또는
# `ceb602c`)에서 PIVOT 이전 버전으로 복원 가능.

variable "region" {
  description = "AWS region. PIVOT으로 prod 미사용이지만 default는 ap-northeast-2 유지."
  type        = string
  default     = "ap-northeast-2"

  validation {
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
    error_message = "학생 계정 제약: us-east-1 차단 (<region-restrict-policy> 정책)."
  }
}

variable "name_prefix" {
  type    = string
  default = "tracker-prod"
}

variable "github_repository" {
  type    = string
  default = "byungju0/261RCOSE45700"
}

variable "tfstate_bucket_name" {
  type    = string
  default = "tracker-tfstate-prod"
}

variable "existing_oidc_provider_arn" {
  description = <<-EOT
    dev 환경에서 만든 GitHub OIDC provider의 ARN.
    PIVOT으로 prod 미사용이지만 변수 인터페이스는 보존.
    dev `terraform output oidc_provider_arn` 값을 여기 주입.
  EOT
  type        = string
  default     = "arn:aws:iam::000000000000:oidc-provider/token.actions.githubusercontent.com"
}
