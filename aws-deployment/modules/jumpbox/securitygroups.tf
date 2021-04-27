### SecurityGroup
resource "aws_security_group" "jumpfed" {
  vpc_id = var.vpc_id
  name   = "${var.basename}-jumpfed-SG"

  description = "SG for jumpfed"

  tags = merge(var.tags, {
    Name = "${var.basename}-jumpfed-SG"
  })
}

### SecurityGroupRule: No outgoing restrictions
resource "aws_security_group_rule" "egress-all" {
  security_group_id = aws_security_group.jumpfed.id

  type = "egress"

  protocol  = "-1"
  from_port = 0
  to_port   = 0

  cidr_blocks = ["0.0.0.0/0"]
}

# SecurityGroupRule: Allow comunication to nodes
resource "aws_security_group_rule" "jumpfed" {
  security_group_id = aws_security_group.jumpfed.id

  description = "Allow jumpfed cluster protocol"

  type      = "ingress"
  protocol  = "tcp"
  from_port = 22
  to_port   = 22

  cidr_blocks = ["0.0.0.0/0"]
}

### Outputs
output "sgjumpfed" { value = aws_security_group.jumpfed.id }

# vim:filetype=terraform ts=2 sw=2 et: