# Builds the backend golden AMI: Amazon Linux 2023 + Docker + the baked
# kpi-backend:latest image + Nginx reverse-proxy config.
# Generic image — NO env-specific values (Terraform injects those at boot).
#
#   cd packer/backend
#   packer init .
#   packer build backend.pkr.hcl
#
# The printed AMI id goes into terraform.tfvars as backend_ami_id.

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
  default = "t3.medium" # RAM for docker build / pip
}


variable "subnet_id" {
  type    = string
  default = ""
}

source "amazon-ebs" "backend" {
  region        = var.region
  instance_type = var.instance_type
  subnet_id     = var.subnet_id != "" ? var.subnet_id : null
  ami_name      = "kpi-backend-ami-{{timestamp}}"
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
    Name    = "kpi-backend-ami"
    Project = "kpi"
    Tier    = "backend"
  }
}

build {
  sources = ["source.amazon-ebs.backend"]

  # Upload the backend source so the image can be built on the box.
  provisioner "file" {
    source      = "${path.root}/../../kpi-automation-backend"
    destination = "/tmp"
  }

  provisioner "shell" {
    script = "${path.root}/../scripts/backend-provision.sh"
  }
}
