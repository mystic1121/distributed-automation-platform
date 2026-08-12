# ===========================================================================
# Security Groups. Each tier only accepts traffic from the tier in
# front of it. All allow default all-outbound.
# ===========================================================================

# ALB: public HTTP from the internet.
resource "aws_security_group" "alb" {
  name        = "kpi-alb-sg"
  description = "ALB - public HTTP"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "kpi-alb-sg" }

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Backend: HTTP only from the ALB.
resource "aws_security_group" "backend" {
  name        = "kpi-backend-sg"
  description = "Backend EC2 - HTTP from ALB only"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "kpi-backend-sg" }

  ingress {
    description     = "HTTP from ALB"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Automation worker: NO inbound (it only pulls from SQS and calls out). Outbound only.
resource "aws_security_group" "automation" {
  name        = "kpi-automation-sg"
  description = "Automation worker - no inbound; SQS/S3/ALB outbound only"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "kpi-automation-sg" }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# RDS: MySQL only from the backend.
resource "aws_security_group" "rds" {
  name        = "kpi-rds-sg"
  description = "RDS - MySQL from backend only"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "kpi-rds-sg" }

  ingress {
    description     = "MySQL from backend"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Jenkins: 8080 + SSH from your admin CIDR.
resource "aws_security_group" "jenkins" {
  name        = "kpi-jenkins-sg"
  description = "Jenkins - 8080 + SSH from admin CIDR"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "kpi-jenkins-sg" }

  ingress {
    description = "Jenkins UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.jenkins_ingress_cidr]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.jenkins_ingress_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
