output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.this.id
}

output "public_ip" {
  description = "Public IP for SSH."
  value       = aws_instance.this.public_ip
}

output "public_dns" {
  description = "Public DNS name."
  value       = aws_instance.this.public_dns
}

output "ec2_role_arn" {
  description = "ARN of the EC2 instance role. Put this in the TRUST POLICY of the cross-account Bedrock role."
  value       = aws_iam_role.instance.arn
}

output "ssh_command" {
  description = "Convenience SSH command (adjust key path)."
  value       = "ssh -i <path-to-your-private-key> ubuntu@${aws_instance.this.public_ip}"
}

output "bootstrap_log_hint" {
  description = "Where to watch the bootstrap install progress."
  value       = "tail -f /var/log/wanderwise-bootstrap.log"
}

output "allowed_ssh_cidr" {
  description = "The CIDR that was granted SSH access."
  value       = local.resolved_ssh_cidr
}
