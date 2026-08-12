# AWS provider. Region comes from var.aws_region (default ap-south-1 / Mumbai).
# Credentials are taken from your local environment (AWS CLI profile / env vars) —
# nothing secret is stored in this repo.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}
