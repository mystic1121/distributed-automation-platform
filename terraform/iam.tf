# ===========================================================================
# IAM roles
# ===========================================================================

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# Backend role
# ---------------------------------------------------------------------------
resource "aws_iam_role" "backend" {
  name               = "ec2-backend-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "backend_ssm" {
  role       = aws_iam_role.backend.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "backend_cw" {
  role       = aws_iam_role.backend.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "backend_inline" {
  statement {
    sid     = "S3"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.storage.arn,
      "${aws_s3_bucket.storage.arn}/*",
    ]
  }
  statement {
    sid       = "Secrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.db.arn, aws_secretsmanager_secret.app.arn]
  }
  statement {
    sid       = "SqsSend"
    actions   = ["sqs:SendMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
    resources = [aws_sqs_queue.jobs.arn]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:CreateLogGroup", "cloudwatch:PutMetricData"]
    resources = ["*"]
  }
  # ECR pull + image-tag read: unused by the AMI-baked boot path, but harmless
  # and ready for the ECR-based pipeline later.
  statement {
    sid       = "EcrPull"
    actions   = ["ecr:GetAuthorizationToken", "ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"]
    resources = ["*"]
  }
  statement {
    sid       = "SsmParams"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project}/*"]
  }
}

resource "aws_iam_role_policy" "backend_inline" {
  name   = "backend-app"
  role   = aws_iam_role.backend.id
  policy = data.aws_iam_policy_document.backend_inline.json
}

resource "aws_iam_instance_profile" "backend" {
  name = "ec2-backend-role"
  role = aws_iam_role.backend.name
}

# ---------------------------------------------------------------------------
# Automation worker role
# ---------------------------------------------------------------------------
resource "aws_iam_role" "automation" {
  name               = "ec2-automation-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "automation_ssm" {
  role       = aws_iam_role.automation.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "automation_cw" {
  role       = aws_iam_role.automation.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "automation_inline" {
  statement {
    sid     = "S3"
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.storage.arn,
      "${aws_s3_bucket.storage.arn}/*",
    ]
  }
  statement {
    sid       = "SqsConsume"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.jobs.arn]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:CreateLogGroup", "cloudwatch:PutMetricData"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "automation_inline" {
  name   = "automation-app"
  role   = aws_iam_role.automation.id
  policy = data.aws_iam_policy_document.automation_inline.json
}

resource "aws_iam_instance_profile" "automation" {
  name = "ec2-automation-role"
  role = aws_iam_role.automation.name
}

# ---------------------------------------------------------------------------
# Jenkins role 
# ---------------------------------------------------------------------------
resource "aws_iam_role" "jenkins" {
  name               = "ec2-jenkins-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "jenkins_ssm" {
  role       = aws_iam_role.jenkins.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "jenkins_inline" {
  statement {
    sid       = "BackendEcrPush"
    actions   = ["ecr:GetAuthorizationToken", "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = ["*"]
  }
  statement {
    sid       = "Params"
    actions   = ["ssm:PutParameter", "ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project}/*"]
  }
  statement {
    sid       = "RollFleets"
    actions   = ["autoscaling:StartInstanceRefresh", "autoscaling:DescribeInstanceRefreshes", "autoscaling:DescribeAutoScalingGroups"]
    resources = ["*"]
  }
  statement {
    sid       = "WorkerRebake"
    actions   = ["ec2:RunInstances", "ec2:TerminateInstances", "ec2:CreateImage", "ec2:CreateTags", "ec2:DescribeInstances", "ec2:DescribeInstanceStatus", "ec2:DescribeImages", "ec2:CreateLaunchTemplateVersion", "ec2:ModifyLaunchTemplate", "ec2:DescribeLaunchTemplates", "ec2:DescribeLaunchTemplateVersions"]
    resources = ["*"]
  }
  statement {
    sid       = "ProvisionBuilder"
    actions   = ["ssm:SendCommand", "ssm:GetCommandInvocation", "ssm:DescribeInstanceInformation"]
    resources = ["*"]
  }
  statement {
    sid       = "PassWorkerRole"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.automation.arn]
  }
}

resource "aws_iam_role_policy" "jenkins_inline" {
  name   = "jenkins-pipeline"
  role   = aws_iam_role.jenkins.id
  policy = data.aws_iam_policy_document.jenkins_inline.json
}

resource "aws_iam_instance_profile" "jenkins" {
  name = "ec2-jenkins-role"
  role = aws_iam_role.jenkins.name
}
