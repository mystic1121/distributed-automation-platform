# ===========================================================================
# Jenkins server. Provisioned and ready
# ===========================================================================

resource "aws_instance" "jenkins" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.jenkins_instance_type
  subnet_id                   = aws_subnet.public["public-a"].id
  vpc_security_group_ids      = [aws_security_group.jenkins.id]
  iam_instance_profile        = aws_iam_instance_profile.jenkins.name
  associate_public_ip_address = true

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  user_data = templatefile("${path.module}/user_data/jenkins.sh.tftpl", {})

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = { Name = "${local.name}-jenkins" }
}
