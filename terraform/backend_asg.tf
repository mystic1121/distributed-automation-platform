# ===========================================================================
# Backend Launch Template + Auto Scaling Group 
# ===========================================================================

resource "aws_launch_template" "backend" {
  name_prefix   = "${local.name}-backend-"
  image_id      = var.backend_ami_id
  instance_type = var.backend_instance_type

  iam_instance_profile {
    name = aws_iam_instance_profile.backend.name
  }

  vpc_security_group_ids = [aws_security_group.backend.id]

  metadata_options {
    http_tokens   = "required" # IMDSv2
    http_endpoint = "enabled"
  }

  user_data = base64encode(templatefile("${path.module}/user_data/backend.sh.tftpl", {
    region            = var.aws_region
    s3_bucket         = aws_s3_bucket.storage.bucket
    db_secret         = aws_secretsmanager_secret.db.name
    app_secret        = aws_secretsmanager_secret.app.name
    sqs_url           = aws_sqs_queue.jobs.url
    alb_dns           = aws_lb.main.dns_name
    company           = var.company
    gunicorn_log_group = aws_cloudwatch_log_group.gunicorn.name
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${local.name}-backend" }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "backend" {
  name                = "${local.name}-backend-asg"
  vpc_zone_identifier = [aws_subnet.private["backend-a"].id, aws_subnet.private["backend-b"].id]
  target_group_arns   = [aws_lb_target_group.backend.arn]

  min_size         = var.backend_asg.min
  desired_capacity = var.backend_asg.desired
  max_size         = var.backend_asg.max

  health_check_type         = "ELB"
  health_check_grace_period = 180

  launch_template {
    id      = aws_launch_template.backend.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
      instance_warmup        = 120
    }
  }

  tag {
    key                 = "Name"
    value               = "${local.name}-backend"
    propagate_at_launch = true
  }

  depends_on = [
    aws_lb_listener.http,
    aws_secretsmanager_secret_version.db,
    aws_secretsmanager_secret_version.app,
  ]
}
