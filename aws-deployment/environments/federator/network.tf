### VPC: DEV
module "vpc" {
  source = "../../modules/vpc/3tier/"

  name = "${var.basename}-vpc"

  cidr = var.vpc_cidr

  public_zones = local.zone_names
  public_bits  = 8
  public_base  = 0

  tags        = {
    "vpc-name" = "${var.basename}-vpc"
  }
  vpc_tags    = {
    "vpc-name" = "${var.basename}-vpc"
  }
}


### VPC Subnets: Worker
module "worker-subnets" {
  source = "../../modules/vpc/subnets/"

  vpc_id = module.vpc.id

  basename = var.basename

  zones  = local.zone_names
  prefix = var.vpc_cidr
  base   = 40

  route_table = module.vpc.rt_private
   tags =  {
    Tier = "Private"
  }
}

### Security Group for ec2 VPC endpoint
resource "aws_security_group" "ec2-endpoint" {
  vpc_id = module.vpc.id

  name        = "${var.basename}-EC2-VPCEP-SG"
  description = "SG for EC2 endpoint endpoint"
}

### Outputs
output "vpc" {
  value = {
    id   = module.vpc.id
    name = module.vpc.name
    cidr = var.vpc_cidr

    rt_default = module.vpc.rt_default
    rt_public  = module.vpc.rt_public
    rt_private = module.vpc.rt_private
    

    natgw_ip = module.vpc.natgw_ip
  }
}

output "private_subnet_ids" { value = module.worker-subnets.ids }

# vim:filetype=terraform ts=2 sw=2 et:
