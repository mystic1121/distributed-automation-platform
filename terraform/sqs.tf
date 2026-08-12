# ===========================================================================
# SQS queues. The backend enqueues job_ids on kpi-jobs; the worker
# fleet long-polls it. Failed-infra jobs land in the DLQ after 3 receives.
# ===========================================================================

resource "aws_sqs_queue" "dlq" {
  name                      = "${local.name}-jobs-dlq"
  message_retention_seconds = 1209600 # 14 days
  tags                      = { Name = "${local.name}-jobs-dlq" }
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${local.name}-jobs"
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20     # long-poll at queue level too

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${local.name}-jobs" }
}
