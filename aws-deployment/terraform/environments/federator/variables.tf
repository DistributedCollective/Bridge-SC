variable "basename" {
}
variable "vpc_cidr" {
}
variable "aws_region" {
  default = "us-east-2"
}
variable "aws_account" {
  default = "500674654096"
}
variable "ubuntu_ami" {
  default = "ami-08962a4068733a2b6"
}

variable "ssh_admin_key"{
  default = "federator"
  
}
variable "federator_ami" {
  default = "ami-07e08246298307d92"
}

variable "federator_instance_type" {
  default = "t3.xlarge"
}
variable "jump_instance_type" {
  default = "t2.micro"
  
}
variable "aws_kms_key" {
  default = "sov-main"
  
}