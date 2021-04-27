export AWS_PROFILE=default
terraform init
terraform apply -auto-approve -var-file=terraform.tfvars
