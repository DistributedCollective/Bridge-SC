### SecurityGroup
resource "aws_security_group" "federator" {
  vpc_id = var.vpc_id
  name   = "${var.basename}-federator-SG"

  description = "SG for federator"

  tags = merge(var.tags, {
    Name = "${var.basename}-federator-SG"
  })
}

### SecurityGroupRule: No outgoing restrictions
resource "aws_security_group_rule" "egress-all" {
  security_group_id = aws_security_group.federator.id

  type = "egress"

  protocol  = "-1"
  from_port = 0
  to_port   = 0

  cidr_blocks = ["0.0.0.0/0"]
}

# SecurityGroupRule: Allow comunication to nodes
resource "aws_security_group_rule" "federator" {
  security_group_id = aws_security_group.federator.id

  description = "Allow federator cluster protocol"

  type      = "ingress"
  protocol  = "tcp"
  from_port = 22
  to_port   = 22

  cidr_blocks = ["0.0.0.0/0"]
}

### Outputs
output "sg" { value = aws_security_group.federator.id }

# vim:filetype=terraform ts=2 sw=2 et: