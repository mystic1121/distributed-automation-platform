# Builds the worker golden AMI: Amazon Linux 2023 + Python 3.11 + worker deps +
# the kpi-automation systemd unit (SQS consumer).
# Generic image — NO env-specific values (Terraform injects those at boot).
#
#   cd packer/worker
#   packer init .
#   packer build worker.pkr.hcl
#
# The printed AMI id goes into terraform.tfvars as worker_ami_id.

packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = "~> 1.3"
    }
  }
}

variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "instance_type" {
  type    = string
  default = "t3.medium"
}

variable "subnet_id" {
  type    = string
  default = ""
}

source "amazon-ebs" "worker" {
  region        = var.region
  instance_type = var.instance_type
  subnet_id     = var.subnet_id != "" ? var.subnet_id : null
  ami_name      = "kpi-automation-ami-{{timestamp}}"
  ssh_username  = "ec2-user"

  associate_public_ip_address = true

  source_ami_filter {
    filters = {
      name                = "al2023-ami-2023.*-x86_64"
      virtualization-type = "hvm"
      root-device-type    = "ebs"
    }
    owners      = ["amazon"]
    most_recent = true
  }

  tags = {
    Name    = "kpi-automation-ami"
    Project = "kpi"
    Tier    = "automation"
  }
}

build {
  sources = ["source.amazon-ebs.worker"]

  provisioner "file" {
    source      = "${path.root}/../../kpi-automation-worker/prepost"
    destination = "/tmp/prepost"
  }

  provisioner "shell" {
    script = "${path.root}/../scripts/worker-provision.sh"
  }
}
