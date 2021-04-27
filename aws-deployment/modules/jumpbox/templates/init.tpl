#cloud-config

# Update the instance on first boot
package_update: true

# Install additional packages
packages:
 - epel-release

# run commands
runcmd:
- yum -y update
- yum -y install ansible
- ansible-playbook --version
- ansible-playbook /var/lib/cloud/instance/boothooks/ansible.yml
