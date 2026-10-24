terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

# Auto-detect the caller's public IP when allowed_ssh_cidr is not provided.
data "http" "my_ip" {
  count = var.allowed_ssh_cidr == "" ? 1 : 0
  url   = "https://checkip.amazonaws.com"
}

locals {
  resolved_ssh_cidr = var.allowed_ssh_cidr != "" ? var.allowed_ssh_cidr : "${trimspace(data.http.my_ip[0].response_body)}/32"
}

# ---------------------------------------------------------------------------
# Latest Deep Learning base AMI (Ubuntu 22.04, NVIDIA driver) resolved via SSM.
# ---------------------------------------------------------------------------
data "aws_ssm_parameter" "dlami" {
  name = "/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id"
}

# Default VPC + a subnet to place the instance in.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ---------------------------------------------------------------------------
# SSH key pair (from your public key).
# ---------------------------------------------------------------------------
resource "aws_key_pair" "this" {
  key_name   = "${var.project}-key"
  public_key = trimspace(file(pathexpand(var.ssh_public_key_path)))
}

# ---------------------------------------------------------------------------
# Security group: SSH from your IP only. App stays bound to localhost on the
# instance (reach it via SSH tunnel), so no app port is exposed publicly.
# ---------------------------------------------------------------------------
resource "aws_security_group" "this" {
  name        = "${var.project}-sg"
  description = "SSH from a single IP; all egress."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [local.resolved_ssh_cidr]
  }

  egress {
    description = "All egress (package installs, HF model download, Bedrock)."
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Project = var.project }
}

# ---------------------------------------------------------------------------
# IAM role for the instance. Baseline: SSM for keyless shell access.
# If bedrock_role_arn is set, allow assuming that cross-account role.
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.project}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
  tags               = { Project = var.project }
}

# Allow Systems Manager Session Manager (shell without opening SSH if desired).
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Permit assuming the cross-account Bedrock role, only when provided.
data "aws_iam_policy_document" "assume_bedrock" {
  count = var.bedrock_role_arn == "" ? 0 : 1
  statement {
    sid       = "AssumeBedrockRole"
    actions   = ["sts:AssumeRole"]
    resources = [var.bedrock_role_arn]
  }
}

resource "aws_iam_role_policy" "assume_bedrock" {
  count  = var.bedrock_role_arn == "" ? 0 : 1
  name   = "${var.project}-assume-bedrock"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.assume_bedrock[0].json
}

resource "aws_iam_instance_profile" "this" {
  name = "${var.project}-instance-profile"
  role = aws_iam_role.instance.name
}

# ---------------------------------------------------------------------------
# The instance. user_data bootstraps ALL installs on the box (nothing local).
# ---------------------------------------------------------------------------
resource "aws_instance" "this" {
  ami                    = data.aws_ssm_parameter.dlami.value
  instance_type          = var.instance_type
  key_name               = aws_key_pair.this.key_name
  vpc_security_group_ids = [aws_security_group.this.id]
  subnet_id              = data.aws_subnets.default.ids[0]
  iam_instance_profile   = aws_iam_instance_profile.this.name

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    bedrock_role_arn = var.bedrock_role_arn
    aws_region       = var.aws_region
  })

  tags = {
    Name    = "${var.project}-host"
    Project = var.project
  }
}
