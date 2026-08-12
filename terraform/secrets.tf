# ===========================================================================
# Secrets Manager. Terraform GENERATES the DB password and Flask key
# and stores them. 
# ===========================================================================

resource "random_password" "db" {
  length  = 24
  special = false 
}

resource "random_password" "flask" {
  length  = 64
  special = false
}

# ---- DB secret (kpi/db) ----------------------------------------------------
# host is filled with the RDS endpoint once the DB exists (see rds.tf reference).
resource "aws_secretsmanager_secret" "db" {
  name        = local.db_secret_name
  description = "RDS MySQL credentials for the KPI backend"
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    host     = aws_db_instance.main.address
    username = var.db_username
    password = random_password.db.result
    dbname   = var.db_name
    port     = 3306
  })
}

# ---- App secret (kpi/app) --------------------------------------------------
resource "aws_secretsmanager_secret" "app" {
  name        = local.app_secret_name
  description = "Flask secret key for the KPI backend"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    flask_secret_key = random_password.flask.result
  })
}
