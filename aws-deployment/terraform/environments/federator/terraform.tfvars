### Environment-specific options
project_env = "STAGE"

# Network-specific options
vpc_cidr = "10.154.0.0/16"

# SSH key for deploying instances in this environemant
ssh_admin_key = "federator"
basename        = "federator"

# ASG: Windows workers

federator_ami = "ami-013f17f36f8b1fefb"

worker_instance_type = "t3.medium"
