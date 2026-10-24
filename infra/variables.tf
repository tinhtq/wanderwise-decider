variable "aws_profile" {
  description = "AWS CLI profile used to provision resources."
  type        = string
}

variable "aws_region" {
  description = "Region to deploy into."
  type        = string
}

variable "project" {
  description = "Project name, used to tag/name resources."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type. A single-GPU type (e.g. g5.2xlarge) suits Decider 2B."
  type        = string
}

variable "ssh_public_key_path" {
  description = "Path to your SSH PUBLIC key file. Used for EC2 login."
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH in. Leave empty to auto-detect your current public IP (/32). Set 0.0.0.0/0 only to open to the world (not recommended)."
  type        = string
  default     = ""
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size in GB (model weights + deps)."
  type        = number
}

variable "bedrock_role_arn" {
  description = "Cross-account IAM role ARN in the Bedrock-enabled account that the EC2 will assume to call Bedrock. Leave empty to use the instance role directly."
  type        = string
  default     = ""
}
