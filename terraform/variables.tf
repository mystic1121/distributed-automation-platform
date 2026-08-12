# ---------------------------------------------------------------------------
# Inputs. The only ones you MUST supply are the two AMI IDs and the alert email
# (see terraform.tfvars.example). Everything else has a sensible default.
# ---------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "Name prefix applied to all resources."
  type        = string
  default     = "kpi"
}

variable "azs" {
  description = "The two Availability Zones to spread across."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

# ---- Golden AMIs (REQUIRED) -------------------------------------------------
# Built by Packer (see ../packer). These are generic images: code + Docker +
# Nginx + systemd units baked in, but NO environment-specific values. Terraform
# injects the env file at boot via the launch-template user-data.

variable "backend_ami_id" {
  description = "AMI ID of the baked backend image (packer/backend.pkr.hcl output)."
  type        = string
}

variable "worker_ami_id" {
  description = "AMI ID of the baked automation-worker image (packer/worker.pkr.hcl output)."
  type        = string
}

# ---- Alerts (REQUIRED) ------------------------------------------------------
variable "alert_email" {
  description = "Email address that receives CloudWatch alarm notifications. You must click the SNS confirmation link once."
  type        = string
}

# ---- Access control ---------------------------------------------------------
variable "jenkins_ingress_cidr" {
  description = "CIDR allowed to reach Jenkins (8080) and SSH (22). Tighten to your IP/32 for security."
  type        = string
  default     = "0.0.0.0/0"
}

# ---- High-availability / cost knobs -----------------------------------------
variable "single_nat_gateway" {
  description = "true = one NAT Gateway (cheaper, less HA). false = one NAT per AZ (matches the diagram)."
  type        = bool
  default     = false
}

variable "rds_multi_az" {
  description = "true = Multi-AZ RDS with a standby (matches the diagram)."
  type        = bool
  default     = true
}

# ---- Compute sizing ---------------------------------------------------------
variable "backend_instance_type" {
  description = "Instance type for the backend ASG."
  type        = string
  default     = "t3.micro"
}

variable "worker_instance_type" {
  description = "Instance type for the automation-worker ASG (needs RAM for Excel/data work)."
  type        = string
  default     = "t3.medium"
}

variable "jenkins_instance_type" {
  description = "Instance type for the Jenkins server."
  type        = string
  default     = "t3.medium"
}

variable "backend_asg" {
  description = "Backend Auto Scaling Group sizing."
  type        = object({ min = number, desired = number, max = number })
  default     = { min = 2, desired = 2, max = 4 }
}

variable "worker_asg" {
  description = "Worker Auto Scaling Group sizing."
  type        = object({ min = number, desired = number, max = number })
  default     = { min = 2, desired = 2, max = 4 }
}

# ---- Database ---------------------------------------------------------------
variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS storage in GB."
  type        = number
  default     = 20
}

variable "db_username" {
  description = "RDS master username."
  type        = string
  default     = "admin"
}

variable "db_name" {
  description = "Initial database name (the app's kpi_automation table is auto-created on first page load)."
  type        = string
  default     = "kpi_db"
}

# ---- Application env ---------------------------------------------------------
variable "company" {
  description = "COMPANY env var the backend reads (multi-company key)."
  type        = string
  default     = "jio"
}

variable "max_concurrent_jobs" {
  description = "Max jobs one worker runs at once (worker MAX_CONCURRENT_JOBS)."
  type        = number
  default     = 5
}

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout (seconds). Must exceed worst-case job runtime; kept in sync with the worker's SQS_VISIBILITY_TIMEOUT."
  type        = number
  default     = 2000
}

# ---- S3 ---------------------------------------------------------------------
variable "s3_bucket_prefix" {
  description = "Prefix for the (globally-unique) storage bucket name. A random suffix is appended."
  type        = string
  default     = "kpi-automation-storage"
}
