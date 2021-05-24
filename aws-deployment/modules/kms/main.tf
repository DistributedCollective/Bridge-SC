### Variables
variable "description" { type = string }
variable "alias_name" { type = string }
variable "tags" { type = map(string) }
variable "policy" { default = "" }
### KMS
resource "aws_kms_key" "key" {
  description         = var.description
  enable_key_rotation = true
  policy = var.policy

  tags = merge(var.tags, {
    Name = "${var.alias_name}-encryption key"
  })
}

# Key alias
resource "aws_kms_alias" "key_alias" {
  name          = "alias/${var.alias_name}"
  target_key_id = aws_kms_key.key.key_id
}

### IAM Policy: key usage
resource "aws_iam_policy" "kms-encrypt-decrypt" {
  name = "${var.alias_name}-KMS-POLICY"
  path = "/"

  policy = <<-EOF
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "kms:Decrypt",
                    "kms:GenerateDataKey"
                ],
                "Resource": "${aws_kms_key.key.arn}"
            }
        ]
    }
    EOF
}

### Outputs
output "kms_key" {
  value = {
    id  = aws_kms_key.key.key_id
    arn = aws_kms_key.key.arn
  }
}

output "kms_alias" {
  value = {
    target_key_arn = aws_kms_alias.key_alias.target_key_arn
    arn            = aws_kms_alias.key_alias.arn
    name           = aws_kms_alias.key_alias.name
  }
}

output "policy_arn" { value = aws_iam_policy.kms-encrypt-decrypt.arn }

# vim:filetype=terraform ts=2 sw=2 et:
