# ===========================================================================
# RDS MySQL. Multi-AZ (var-controlled). 
# ===========================================================================

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db-subnet-group"
  subnet_ids = [for s in aws_subnet.db : s.id]
  tags       = { Name = "${local.name}-db-subnet-group" }
}

resource "aws_db_instance" "main" {
  identifier     = "${local.name}-db"
  engine         = "mysql"
  engine_version = "8.0"
  instance_class = var.db_instance_class

  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result
  port     = 3306

  multi_az               = var.rds_multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  enabled_cloudwatch_logs_exports = ["error", "slowquery"]

  skip_final_snapshot = true
  deletion_protection = false

  tags = { Name = "${local.name}-db" }
}
