module "federator" {
  source      = "../../modules/federator-ec2"
  basename    = var.basename
  aws_region  = var.aws_region
  aws_account = var.aws_account

  vpc_id  = module.vpc.id
  
  subnets = [module.worker-subnets.ids[0], module.worker-subnets.ids[1], module.worker-subnets.ids[2]]
  eip     = true

  instance_ami = var.federator_ami

  ssh_key             = var.ssh_admin_key
  instance_type       = var.federator_instance_type
  instance_block_size = 50
  server_count        = 3
  tags                = {
    "Name" = "${var.basename}-instance"
  }

  encryption_enabled  = "enabled"
  kms_key_id          = aws_kms_key.main.arn
}

module "jumpbox" {
  source      = "../../modules/jumpbox"
  basename    = var.basename
  aws_region  = var.aws_region
  aws_account = var.aws_account

  vpc_id  = module.vpc.id
  
  subnets = [module.vpc.public_subnets.ids[0], module.vpc.public_subnets.ids[1],  module.vpc.public_subnets.ids[2]]
  eip     = true

  instance_ami = var.ubuntu_ami

  ssh_key             = var.ssh_admin_key
  instance_type       = var.jump_instance_type
  instance_block_size = 50
  server_count        = 1
  tags                = {
    "Name" = "${var.basename}-instance"
  }

  encryption_enabled  = "enabled"
  kms_key_id          = aws_kms_key.main.arn
}

### Output endpoints
output "federator" { value = module.federator.federator_instances }
output "jump-fed" { value = module.jumpbox.fed-jumpbox }

# vim:filetype=terraform ts=2 sw=2 et:
