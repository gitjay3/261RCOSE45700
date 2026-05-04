variable "env" {
  description = "Environment name (dev | prod). Determines tfstate bucket suffix."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be one of: dev, prod."
  }
}

variable "region" {
  description = <<-EOT
    AWS region. Default: ap-northeast-2(Seoul).
    학생 계정 SCP `<region-restrict-policy>`로 us-east-1만 차단. 나머지 16개 region 허용.
  EOT
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
    error_message = "학생 계정 제약: region이 학교 허용 화이트리스트에 없음 (us-east-1만 차단)."
  }
}
