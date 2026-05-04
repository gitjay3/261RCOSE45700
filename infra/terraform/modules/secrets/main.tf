terraform {
  required_version = ">= 1.14, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

##
# Secrets — placeholder만 정의. 실제 값은:
#   - rds_admin_password : RDS 모듈이 random_password로 자동 주입 (Task 6)
#   - varco_api_key      : Console 또는 ops 스크립트로 1회 주입
#   - proxy_credentials  : Console 또는 ops 스크립트로 1회 주입
#
# 평문 값은 절대 Terraform 변수/tfvars에 두지 않는다 (NFR5, deferred-work 안티패턴).
#
# 학생 계정 PIVOT — KMS는 AWS-managed `alias/aws/secretsmanager` 자동 사용
# (kms_key_id 미지정 시 default 동작). KMS CMK 생성 권한 부족 가정 + 학생
# 프로젝트 범위 외라 별도 CMK 미생성.
##

resource "aws_secretsmanager_secret" "varco_api_key" {
  name                    = "${var.name_prefix}/varco-api-key"
  description             = "VARCO LLM API key — 값은 Console 또는 ops 스크립트로 1회 주입"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, { Module = "secrets", Purpose = "varco-api-key" })
}

resource "aws_secretsmanager_secret" "rds_admin_password" {
  name                    = "${var.name_prefix}/rds-admin-password"
  description             = "RDS master password — RDS 모듈이 random_password로 자동 주입"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, { Module = "secrets", Purpose = "rds-admin-password" })
}

resource "aws_secretsmanager_secret" "proxy_credentials" {
  name                    = "${var.name_prefix}/proxy-credentials"
  description             = "Proxy(IPRoyal/ThorData) credentials — 값은 Console 또는 ops 스크립트로 1회 주입"
  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(var.tags, { Module = "secrets", Purpose = "proxy-credentials" })
}
