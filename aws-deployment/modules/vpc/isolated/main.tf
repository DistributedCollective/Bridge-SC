### Variables
variable "cidr"  { type = string }
variable "name"  { type = string }

variable "tags" {
  type    = map(string)
  default = {}
}

variable "vpc_tags" {
  type    = map(string)
  default = {}
}

### VPC
resource "aws_vpc" "vpc" {
  cidr_block           = var.cidr
  enable_dns_hostnames = true

  tags = merge(var.tags, var.vpc_tags, {
    Name = "${var.name}-VPC"
  })
}

### Default Route Table
resource "aws_default_route_table" "vpc" {
  default_route_table_id = aws_vpc.vpc.default_route_table_id

  tags = merge(var.tags, {
    Name = "${var.name}-Default-RT"
  })
}

### Outputs
output "id"         { value = aws_vpc.vpc.id }
output "name"       { value = var.name }
output "rt_default" { value = aws_vpc.vpc.default_route_table_id }

# vim:filetype=terraform ts=2 sw=2 et:
