### KMS Key
resource "aws_kms_key" "main" {
  description = "KMS Key for fed disk"

  enable_key_rotation = true

  policy = <<-EOF
    {
      "Version": "2012-10-17",
      "Id": "1",
      "Statement": [
        {
          "Sid": "Enable IAM User Permissions",
          "Effect": "Allow",
          "Principal": {"AWS": "arn:aws:iam::${var.aws_account}:root"},
          "Action": "kms:*",
          "Resource": "*"
        },
        {
          "Sid": "Allow key usage via S3 service",
          "Effect": "Allow",
          "Principal": {"AWS": "arn:aws:iam::${var.aws_account}:root"},
          "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
          "Resource": "*",
          "Condition": {"StringEquals": {"kms:ViaService": "s3.amazonaws.com"}}
        },
        {
          "Sid": "Allow service-linked role use of the CMK",
          "Effect": "Allow",
          "Principal": {
            "AWS": "arn:aws:iam::${var.aws_account}:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling"
          },
          "Action": [
            "kms:Encrypt",
            "kms:Decrypt",
            "kms:ReEncrypt*",
            "kms:GenerateDataKey*",
            "kms:DescribeKey"
          ],
          "Resource": "*"
        },
        {
          "Sid": "Allow attachment of persistent resources",
          "Effect": "Allow",
          "Principal": {
            "AWS": "arn:aws:iam::${var.aws_account}:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling"
          },
          "Action": "kms:CreateGrant",
          "Resource": "*",
          "Condition": {"Bool": {"kms:GrantIsForAWSResource": "true"}}
        }
      ]
    }
    EOF

  tags = {
    "Name" = "${var.basename}-KEY"
  }
}

# KMS Key Alias
resource "aws_kms_alias" "main" {
  name          = "alias/${var.basename}-KEY"
  target_key_id = aws_kms_key.main.key_id
}

# IAM Policy: Allow key usage
resource "aws_iam_policy" "kms-main-usage" {
  name = "${var.basename}-KEY-POLICY"
  path = "/"

  policy = <<-EOF
    {
      "Version": "2012-10-17",
      "Statement": [
          {
            "Effect": "Allow",
            "Action": [
              "kms:Decrypt",
              "kms:GenerateDataKey*",
              "kms:CreateGrant",
              "kms:Describe*",
              "kms:Encrypt",
              "kms:ReEncrypt*"
            ],
            "Resource": "${aws_kms_key.main.arn}"
          }
      ]
    }
    EOF
}

### Outputs
output "kms_key" {
  value = {
    id    = aws_kms_key.main.id
    arn   = aws_kms_key.main.arn
    alias = aws_kms_alias.main.id
    policy = {
      arn  = aws_iam_policy.kms-main-usage.arn
      name = aws_iam_policy.kms-main-usage.name
    }
  }
}

# vim:filetype=terraform ts=2 sw=2 et:
