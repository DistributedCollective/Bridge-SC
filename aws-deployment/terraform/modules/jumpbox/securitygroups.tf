### SecurityGroup
resource "aws_security_group" "fed-jumpbox" {
  vpc_id = var.vpc_id
  name   = "${var.basename}-fed-jumpbox-SG"

  description = "SG for fed-jumpbox"

  ingress {
    description = "ssh public"
    from_port = 0
    to_port   = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.basename}-fed-jumpbox-SG"
  })
}


### Outputs
output "sg" { value = aws_security_group.fed-jumpbox.id }

# vim:filetype=terraform ts=2 sw=2 et: