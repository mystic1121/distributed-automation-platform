# ===========================================================================
# S3 bucket. Private; reached via the VPC gateway endpoint. 
# ===========================================================================

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "storage" {
  bucket = "${var.s3_bucket_prefix}-${random_id.bucket_suffix.hex}"
  tags   = { Name = "${local.name}-storage" }
}

resource "aws_s3_bucket_public_access_block" "storage" {
  bucket                  = aws_s3_bucket.storage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "storage" {
  bucket = aws_s3_bucket.storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Seed the config files the app expects at the bucket root.
# Paths are relative to the terraform/ directory.
resource "aws_s3_object" "mapping" {
  bucket = aws_s3_bucket.storage.id
  key    = "mapping.json"
  source = "${path.module}/../89-Storage Server/mapping.json"
  etag   = filemd5("${path.module}/../89-Storage Server/mapping.json")
}

resource "aws_s3_object" "templates_config" {
  bucket = aws_s3_bucket.storage.id
  key    = "templates_config.json"
  source = "${path.module}/../89-Storage Server/templates_config.json"
  etag   = filemd5("${path.module}/../89-Storage Server/templates_config.json")
}
