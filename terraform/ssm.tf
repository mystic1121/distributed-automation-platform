# ===========================================================================
# SSM Parameters consumed by the (later) Jenkins pipeline:
#   /kpi/backend/image-tag  -> which ECR tag the backend fleet should run
#   /kpi/automation/ami-id  -> the AMI the next worker rebake builds FROM
# ===========================================================================

resource "aws_ssm_parameter" "backend_image_tag" {
  name  = "/${var.project}/backend/image-tag"
  type  = "String"
  value = "bootstrap"

  # Jenkins overwrites this each deploy; don't fight it on re-apply.
  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "automation_ami_id" {
  name  = "/${var.project}/automation/ami-id"
  type  = "String"
  value = var.worker_ami_id

  lifecycle {
    ignore_changes = [value]
  }
}
