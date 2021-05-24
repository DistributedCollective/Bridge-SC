### Variables
variable "basename" { type = string }
variable "aws_region" { type = string }
variable "aws_account" { type = string }
variable "vpc_id" { type = string }
variable "subnets" { type = list(string) }
variable "instance_ami" { type = string }
variable "instance_type" { type = string }
variable "instance_block_size" { type = number }
variable "ssh_key" { type = string }
variable "server_count" { default = 2 }
variable "tags" { default = {} }


variable "encryption_enabled" {
  default = "false"
}

variable "eip" { default = false }

# Choose random pool subnets of all for SFTP
resource "random_shuffle" "subnets" {
  input = var.subnets

  result_count = var.server_count
}

# Render a init part
data "template_file" "init" {
  template = "${file("${path.module}/templates/init.tpl")}"
}

# Render an ansible part
data "template_file" "ansible_playbook_yml" {
  template = "${file("${path.module}/ansible/ansible.yml")}"

  vars = {
    aws_region    = var.aws_region
  }
}

# Render a multi-part cloud-init config making use of the part
# above, and other source files
data "template_cloudinit_config" "config" {
  gzip          = true
  base64_encode = true
  # Ansible playbook file.

  part {
    filename     = "ansible.yml"
    content_type = "text/cloud-boothook"
    content      = "${data.template_file.ansible_playbook_yml.rendered}"
  }

  # Main cloud-config configuration file.
  part {
    filename     = "init.cfg"
    content_type = "text/cloud-config"
    content      = "${data.template_file.init.rendered}"
  }
}





### EC2 Instances: fed-jumpbox servers
resource "aws_instance" "fed-jumpbox" {
  count = var.server_count

  ami = var.instance_ami

  subnet_id = random_shuffle.subnets.result[0]

  associate_public_ip_address = true

  vpc_security_group_ids = [aws_security_group.jumpfed.id]

  # Optional: comment out if not required
  # iam_instance_profile = aws_iam_instance_profile.main.name

  instance_type = var.instance_type
  key_name      = var.ssh_key
  monitoring    = true

  root_block_device {
    volume_type = "gp2"
    volume_size = var.instance_block_size
    encrypted = false
  }

  user_data = data.template_cloudinit_config.config.rendered

  lifecycle {
    ignore_changes = [ami]
  }

  tags = {
    Name = "fed-jumpbox"
  }

  volume_tags = merge(var.tags, {
    Name = "${var.basename}-fed-jumpbox-vol-${count.index + 1}"
  })

  disable_api_termination = false
  ebs_optimized           = false
}

resource "aws_security_group" "fed-jumpbox-sec" {
  name        = format("%s-fed-jumpbox-sec", var.basename)
  description = "federtar Security Group"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.basename}-fed-jumpbox-sec-tg"
  })
}


resource "aws_security_group_rule" "ingress" {
  type                     = "ingress"
  from_port                = "22" # NFS
  to_port                  = "22"
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.jumpfed.id
  security_group_id        = join("", aws_security_group.jumpfed.*.id)
}

### Outputs
output "fed-jumpbox" { 
  value = aws_instance.fed-jumpbox.*.id 
  }

# vim:filetype=terraform ts=2 sw=2 et:
