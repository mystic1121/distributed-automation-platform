data "aws_caller_identity" "current" {}

# Latest Amazon Linux 2023 AMI — used only for the Jenkins box (the backend and
# worker use your Packer-baked AMIs). Looked up automatically; no input needed.
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  name        = var.project
  account_id  = data.aws_caller_identity.current.account_id
  nat_count   = var.single_nat_gateway ? 1 : length(var.azs)

  # 8 subnets, mirroring the build guide's table.
  public_subnets = {
    public-a = { az = var.azs[0], cidr = "10.0.1.0/24" }
    public-b = { az = var.azs[1], cidr = "10.0.2.0/24" }
  }

  # Private app/worker subnets, grouped by AZ index so each maps to its AZ's NAT.
  private_subnets = {
    backend-a    = { az = var.azs[0], cidr = "10.0.3.0/24", az_index = 0 }
    backend-b    = { az = var.azs[1], cidr = "10.0.4.0/24", az_index = 1 }
    automation-a = { az = var.azs[0], cidr = "10.0.5.0/24", az_index = 0 }
    automation-b = { az = var.azs[1], cidr = "10.0.6.0/24", az_index = 1 }
  }

  db_subnets = {
    db-a = { az = var.azs[0], cidr = "10.0.7.0/24", az_index = 0 }
    db-b = { az = var.azs[1], cidr = "10.0.8.0/24", az_index = 1 }
  }

  # Secrets Manager secret names the app references via DB_SECRET_ID / APP_SECRET_ID.
  db_secret_name  = "${var.project}/db"
  app_secret_name = "${var.project}/app"
}
