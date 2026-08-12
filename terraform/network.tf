# ===========================================================================
# Phase B — Networking: VPC, 8 subnets, IGW, NAT Gateways, route tables,
# S3 gateway endpoint.
# ===========================================================================

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.name}-vpc" }
}

# ---- Subnets ---------------------------------------------------------------
resource "aws_subnet" "public" {
  for_each                = local.public_subnets
  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true
  tags                    = { Name = each.key, Tier = "public" }
}

resource "aws_subnet" "private" {
  for_each          = local.private_subnets
  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az
  tags              = { Name = each.key, Tier = "private" }
}

resource "aws_subnet" "db" {
  for_each          = local.db_subnets
  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az
  tags              = { Name = each.key, Tier = "db" }
}

# ---- Internet Gateway ------------------------------------------------------
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-igw" }
}

# ---- NAT Gateways -----
resource "aws_eip" "nat" {
  count  = local.nat_count
  domain = "vpc"
  tags   = { Name = "${local.name}-nat-eip-${count.index}" }
}

resource "aws_nat_gateway" "main" {
  count         = local.nat_count
  allocation_id = aws_eip.nat[count.index].id
  # NAT lives in a public subnet; index 0 -> public-a, index 1 -> public-b.
  subnet_id     = element([aws_subnet.public["public-a"].id, aws_subnet.public["public-b"].id], count.index)
  tags          = { Name = "nat-${element(["a", "b"], count.index)}" }
  depends_on    = [aws_internet_gateway.main]
}

# ---- Route tables ----------------------------------------------------------
# Public: out to the internet via the IGW.
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "rt-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# Private AZ-a: outbound via nat[0].
resource "aws_route_table" "private_a" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "rt-private-a" }
}

resource "aws_route" "private_a_nat" {
  route_table_id         = aws_route_table.private_a.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[0].id
}

# Private AZ-b: outbound via nat[1]
resource "aws_route_table" "private_b" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "rt-private-b" }
}

resource "aws_route" "private_b_nat" {
  route_table_id         = aws_route_table.private_b.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = var.single_nat_gateway ? aws_nat_gateway.main[0].id : aws_nat_gateway.main[1].id
}

locals {
  private_rt_by_az = {
    0 = aws_route_table.private_a.id
    1 = aws_route_table.private_b.id
  }
}

# Associate every private app + db subnet with its AZ's private route table.
resource "aws_route_table_association" "private" {
  for_each       = local.private_subnets
  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = local.private_rt_by_az[each.value.az_index]
}

resource "aws_route_table_association" "db" {
  for_each       = local.db_subnets
  subnet_id      = aws_subnet.db[each.key].id
  route_table_id = local.private_rt_by_az[each.value.az_index]
}

# ---- S3 Gateway Endpoint (free private path to S3, no NAT charges) ---------
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private_a.id, aws_route_table.private_b.id]
  tags              = { Name = "${local.name}-s3-endpoint" }
}
