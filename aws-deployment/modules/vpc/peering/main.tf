### Inputs
variable "name" { type = string }

# Local VPC info
variable "local_region"       { type = string }
variable "local_vpc_id"       { type = string }
variable "local_vpc_cidr"     { default = "" }

variable "local_route_tables" {
  type    = list(string)
  default = []
}

# Peer VPC info
variable "peer_region"   { type = string }
variable "peer_vpc_id"   { type = string }
variable "peer_vpc_cidr" { default = "" }

variable "peer_route_tables" {
  type    = list(string)
  default = []
}

# Extra tags for all resources
variable "tags" {
  type    = map(string)
  default = {}
}

### Providers proxy configuration
provider "aws" { alias = "local" }
provider "aws" { alias = "peer" }

### Locals
locals {
  pcx_tags = merge(var.tags, {
    Name = "${var.name}-PCX"
  })
}

### VPC Peering Connection
resource "aws_vpc_peering_connection" "pcx" {
  provider = aws.local

  vpc_id = var.local_vpc_id

  peer_region = var.peer_region
  peer_vpc_id = var.peer_vpc_id

  tags = local.pcx_tags
}

### VPC Peering Accepter
resource "aws_vpc_peering_connection_accepter" "pcx" {
  provider = aws.peer

  vpc_peering_connection_id = aws_vpc_peering_connection.pcx.id

  auto_accept = true

  tags = local.pcx_tags
}

### Allow mutual DNS resolution
# For local VPC...
resource "aws_vpc_peering_connection_options" "local" {
  provider = aws.local

  vpc_peering_connection_id = aws_vpc_peering_connection.pcx.id

  # Set peering connection options
  requester {
    allow_remote_vpc_dns_resolution  = true
    allow_classic_link_to_remote_vpc = false
    allow_vpc_to_remote_classic_link = false
  }

  # Ignore the other side - it won't work cross-region
  lifecycle {
    ignore_changes = [ accepter ]
  }

  depends_on = [aws_vpc_peering_connection_accepter.pcx]
}

# For peer VPC...
resource "aws_vpc_peering_connection_options" "peer" {
  provider = aws.peer

  vpc_peering_connection_id = aws_vpc_peering_connection.pcx.id

  # Set peering connection options
  accepter {
    allow_remote_vpc_dns_resolution  = true
    allow_classic_link_to_remote_vpc = false
    allow_vpc_to_remote_classic_link = false
  }

  # Ignore the other side - it won't work cross-region
  lifecycle {
    ignore_changes = [ requester ]
  }

  depends_on = [aws_vpc_peering_connection_accepter.pcx]
}

### Local Routing tables rule
resource "aws_route" "local-pcx" {
  count = length(var.local_route_tables)

  provider = aws.local

  # Getting element via [count.index] doesn't work here
  route_table_id = element(var.local_route_tables, count.index)

  destination_cidr_block    = var.peer_vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.pcx.id

  depends_on = [aws_vpc_peering_connection_accepter.pcx]
}

### Peer Routing tables rule
resource "aws_route" "peer-pcx" {
  count = length(var.peer_route_tables)

  provider = aws.peer

  # Getting element via [count.index] doesn't work here
  route_table_id = element(var.peer_route_tables, count.index)

  destination_cidr_block    = var.local_vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.pcx.id

  depends_on = [aws_vpc_peering_connection_accepter.pcx]
}

### Outputs
output "pcx_id" { value = aws_vpc_peering_connection.pcx.id }

# vim:filetype=terraform ts=2 sw=2 et:
