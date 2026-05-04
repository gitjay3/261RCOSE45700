terraform {
  required_version = ">= 1.14, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# 학생 계정 PIVOT — Amazon Linux 2023 x86_64 (Graviton arm64 미가용)
data "aws_ami" "al2023_x86_64" {
  count       = var.ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

locals {
  ami_id = var.ami_id != "" ? var.ami_id : data.aws_ami.al2023_x86_64[0].id
}

module "ec2" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.4"

  name = var.service_name

  ami           = local.ami_id
  instance_type = var.instance_type
  subnet_id     = var.subnet_id

  vpc_security_group_ids      = [var.security_group_id]
  iam_instance_profile        = var.iam_instance_profile
  associate_public_ip_address = var.associate_public_ip_address

  # IMDSv2 강제 — Checkov CKV_AWS_79
  metadata_options = {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "enabled"
  }

  # ec2-instance v6.4.0: root_block_device는 single object (list X), 필드명 type/size로 변경
  root_block_device = {
    encrypted = true
    type      = "gp3"
    size      = var.root_volume_size_gb
    tags      = merge(var.tags, { Name = "${var.service_name}-root" })
  }

  user_data                   = var.user_data
  user_data_replace_on_change = false

  tags = merge(
    var.tags,
    {
      Service = var.service_name
      Module  = "ec2-service"
    },
  )
}
