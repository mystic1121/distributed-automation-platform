# ===========================================================================
# Useful values after `terraform apply`.
# ===========================================================================

output "app_url" {
  description = "Open this in a browser — your application's public URL."
  value       = "http://${aws_lb.main.dns_name}"
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "s3_bucket" {
  description = "Storage bucket name (replaces the old Z:\\ drive)."
  value       = aws_s3_bucket.storage.bucket
}

output "sqs_queue_url" {
  value = aws_sqs_queue.jobs.url
}

output "sqs_dlq_url" {
  value = aws_sqs_queue.dlq.url
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "db_secret_name" {
  value = aws_secretsmanager_secret.db.name
}

output "app_secret_name" {
  value = aws_secretsmanager_secret.app.name
}

output "ecr_backend_repo" {
  value = aws_ecr_repository.backend.repository_url
}

output "jenkins_url" {
  description = "Jenkins UI. Unlock with the initial admin password on the box."
  value       = "http://${aws_instance.jenkins.public_ip}:8080"
}

output "backend_asg_name" {
  value = aws_autoscaling_group.backend.name
}

output "automation_asg_name" {
  value = aws_autoscaling_group.automation.name
}

output "reminder" {
  value = "ACTION REQUIRED: confirm the SNS subscription email sent to ${var.alert_email} so alarms can notify you."
}
