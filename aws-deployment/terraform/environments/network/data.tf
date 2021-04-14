### Data sources

# Availability zones
data "aws_availability_zones" "aws_azs" {}

# # Latest CentOS 7 AMI in the region (needs manual subscription)
# data "aws_ami" "ubuntu" {
#   executable_users = ["all"]
#   owners           = ["aws-marketplace"]
#   most_recent      = true

#   filter {
#     name   = "virtualization-type"
#     values = ["hvm"]
#   }

#   filter {
#     name   = "architecture"
#     values = ["x86_64"]
#   }

#   filter {
#     name   = "owner-id"
#     values = ["500674654096"]
#   }

#   filter {
#     name   = "product-code"
#     values = ["aw0evgkw8e5c1q413zgy5pjce"]
#   }
# }

# # MGMT remote state
# data "terraform_remote_state" "mgmt" {
#   backend = "s3"
#   config = {
#     region = var.tfstate_region
#     bucket = var.tfstate_bucket
#     key    = "environments/us-mgmt/terraform.tfstate"
#   }
# }

### Handy locals
locals {
  zone_names = data.aws_availability_zones.aws_azs.names
  zone_ids   = data.aws_availability_zones.aws_azs.zone_ids

  # ubuntu_ami = data.aws_ami.ubuntu.image_id

  # mgmt_tgw = data.terraform_remote_state.mgmt.outputs.tgw
  # mgmt_vpc = data.terraform_remote_state.mgmt.outputs.vpc

  # es_private_lb = data.terraform_remote_state.mgmt.outputs.elasticsearch.private_lb

  # jenkins_role = data.terraform_remote_state.mgmt.outputs.jenkins.role
}

# vim:filetype=terraform ts=2 sw=2 et:
