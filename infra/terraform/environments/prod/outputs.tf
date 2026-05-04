output "vpc_id" {
  value = module.networking.vpc_id
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "archive_bucket_name" {
  value = module.s3_archive.bucket_name
}

output "ec2_crawler_id" {
  value = module.ec2_crawler.instance_id
}

output "ec2_detection_id" {
  value = module.ec2_detection.instance_id
}

output "ec2_api_id" {
  value = module.ec2_api.instance_id
}

output "ec2_api_public_ip" {
  value = module.ec2_api.public_ip
}

output "github_actions_role_arn" {
  description = "prod GitHub Actions OIDC assume role ARN — apply-prod 잡(if:false 비활성)에서만 참조."
  value       = module.iam.github_actions_role_arn
}

# NOTE: cloudtrail_bucket output은 PIVOT으로 security-baseline 모듈 비활성되어 제거.
# CloudTrail은 학교 organization trail에 의존.
