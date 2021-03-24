variable "basename" {
}
variable "vpc_cidr" {
}
variable "aws_region" {
  default = "us-east-1"
}
variable "aws_account" {
  default = "500674654096"
}
variable "ubuntu_ami" {
  default = "ami-013f17f36f8b1fefb"
}
variable "ssh_admin_key" {
  default = "bitnami-OR6YoRE"
}

variable "federator_instance_type" {
  default = "t2.micro"
  
}
variable "aws_kms_key" {
  default = "sov-main"
  
}
