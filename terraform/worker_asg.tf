# ===========================================================================
# Worker Launch Template + Auto Scaling Group.
# ===========================================================================

resource "aws_launch_template" "worker" {
  name_prefix   = "${local.name}-automation-"
  image_id      = var.worker_ami_id
  instance_type = var.worker_instance_type

  iam_instance_profile {
    name = aws_iam_instance_profile.automation.name
  }

  vpc_security_group_ids = [aws_security_group.automation.id]

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  user_data = base64encode(templatefile("${path.module}/user_data/worker.sh.tftpl", {
    region                 = var.aws_region
    s3_bucket              = aws_s3_bucket.storage.bucket
    sqs_url                = aws_sqs_queue.jobs.url
    alb_dns                = aws_lb.main.dns_name
    max_concurrent_jobs    = var.max_concurrent_jobs
    sqs_visibility_timeout = var.sqs_visibility_timeout
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${local.name}-automation" }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "automation" {
  name                = "${local.name}-automation-asg"
  vpc_zone_identifier = [aws_subnet.private["automation-a"].id, aws_subnet.private["automation-b"].id]

  min_size         = var.worker_asg.min
  desired_capacity = var.worker_asg.desired
  max_size         = var.worker_asg.max

  health_check_type         = "EC2"
  health_check_grace_period = 120

  launch_template {
    id      = aws_launch_template.worker.id
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
    value               = "${local.name}-automation"
    propagate_at_launch = true
  }
}

# Target-tracking scaling on backlog per instance:
#   (messages visible in kpi-jobs) / (in-service workers)  ->  target 5.
resource "aws_autoscaling_policy" "worker_backlog" {
  name                   = "${local.name}-automation-backlog-per-instance"
  autoscaling_group_name = aws_autoscaling_group.automation.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    target_value = 5

    customized_metric_specification {
      metrics {
        id          = "m1"
        label       = "Messages visible"
        return_data = false
        metric_stat {
          stat = "Average"
          metric {
            namespace   = "AWS/SQS"
            metric_name = "ApproximateNumberOfMessagesVisible"
            dimensions {
              name  = "QueueName"
              value = aws_sqs_queue.jobs.name
            }
          }
        }
      }
      metrics {
        id          = "m2"
        label       = "In-service workers"
        return_data = false
        metric_stat {
          stat = "Average"
          metric {
            namespace   = "AWS/AutoScaling"
            metric_name = "GroupInServiceInstances"
            dimensions {
              name  = "AutoScalingGroupName"
              value = aws_autoscaling_group.automation.name
            }
          }
        }
      }
      metrics {
        id          = "e1"
        label       = "Backlog per instance"
        expression  = "m1 / m2"
        return_data = true
      }
    }
  }
}
