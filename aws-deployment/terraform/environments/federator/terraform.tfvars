### Environment-specific options
project_env = "PROD"

# Network-specific options
vpc_cidr = "10.154.0.0/16"

# SSH key for deploying instances in this environemant
ssh_admin_key = "federator"
basename        = "federator-PROD"

# ASG: Windows workers

federator_ami = "ami-07e08246298307d92"

worker_instance_type = "t3.medium"
