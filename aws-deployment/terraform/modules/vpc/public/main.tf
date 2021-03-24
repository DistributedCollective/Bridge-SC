### Variables
variable "name" { type = string }
variable "cidr" { type = string }

# Public subnet parameters: availability zones to cover, base and bits
variable "public_zones" { type = list(string) }
variable "public_base"  { default = 0 }
variable "public_bits"  { default = 8 }

# Tags for all resources
variable "tags" { type = map(string) }

# Additional tags to assign to VPC and public subnets
variable "vpc_tags" { default = {} }

# Additional tags to assign to public subnets
variable "public_tags" { default = {} }

### VPC: Isolated VPC
module "vpc" {
  source = "../isolated/"

  name = var.name
  cidr = var.cidr

  tags     = var.tags
  vpc_tags = var.vpc_tags
}

### Route Table: Public
resource "aws_route_table" "public" {
  vpc_id = module.vpc.id
  tags = merge(var.tags, {
    Name = "${var.name}-Public-RT"
    Tier = "Public"
  })
}

# Internet gateway
resource "aws_internet_gateway" "igw" {
  vpc_id = module.vpc.id

  tags = merge(var.tags, {
    Name = "${var.name}-Public-IGW"
    Tier = "Public"
  })
}

# Route: Default via igw
resource "aws_route" "public-igw" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

### Subnets: Public subnets
module "public-subnets" {
  source = "../subnets/"

  vpc_id   = module.vpc.id
  basename = "${var.name}-Public"

  zones  = var.public_zones
  prefix = var.cidr
  bits   = var.public_bits
  base   = var.public_base

  route_table = aws_route_table.public.id

  tags = merge(var.tags, var.vpc_tags, var.public_tags, {
    Tier = "Public"
  })
}

### Outputs
output "id"         { value = module.vpc.id }
output "name"       { value = module.vpc.name }

output "rt_default" { value = module.vpc.rt_default }
output "rt_public"  { value = aws_route_table.public.id }

output "public_subnets" {
  value = {
    ids = module.public-subnets.ids
    azs = module.public-subnets.azs
  }

  # Ensure that the result is not returned until IGW is attached
  # Required to add NAT Gateway
  depends_on = [aws_route.public-igw]
}


output "private_subnets" {
  value = {
    ids = module.public-subnets.ids
    azs = module.public-subnets.azs
  }

  # Ensure that the result is not returned until IGW is attached
  # Required to add NAT Gateway
  depends_on = [aws_route.public-igw]
}


# vim:filetype=terraform ts=2 sw=2 et:
