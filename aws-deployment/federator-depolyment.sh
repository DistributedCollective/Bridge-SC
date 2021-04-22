cd 
sudo apt update
sudo apt install -y wget unzip git sudo curl
wget https://releases.hashicorp.com/terraform/0.12.29/terraform_0.12.29_linux_amd64.zip
unzip terraform_0.12.29_linux_amd64.zip
cp -rf terraform /usr/bin/
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
git clone https://github.com/DistributedCollective/Bridge-SC.git
cd /root/Bridge-SC/aws-deployment/terraform/environments/federator
terraform init
terraform 
terraform apply -auto-approve -var-file=terraform.tfvars