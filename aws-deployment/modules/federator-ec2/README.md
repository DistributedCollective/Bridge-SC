## MODULE: SFTP-EC2
### General

Copyright (c) 2020 Automat-IT
#
### Module details
Module parameters are:

* ``basename``,  ``tags``
  Base name and tags to assign to the resources.

* ``vpc_id``, ``subnets``
  VPC and subnets to place the service endpoints.

* ``count_slave`` (default = 2)
  The number of the slave instances. 

* ``ssh_key``
  SSH-key for instances.

* ``instance_ami``, ``instance_type``, ``instance_block_size``
  AMI, type of instance, volume size for the instances. 

* ``indexes_prefix``, ``indexes_retention_period`` (default=30)
  Index prefix and index retention period (days)	

Outputs parameters are:

* ``sg``
  Security Group of the instances.

#
#### Additional links:
Cloudinit - execution order of cloud-config directives: 
* https://stackoverflow.com/questions/34095839/cloud-init-what-is-the-execution-order-of-cloud-config-directives
* https://git.launchpad.net/cloud-init/tree/config/cloud.cfg.tmpl
