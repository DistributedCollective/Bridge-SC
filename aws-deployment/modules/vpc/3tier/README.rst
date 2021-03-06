==================
MODULE: 3-tier VPC
==================

General
=======

This module creates a basic VPC with public subnets in each availability zone, adds an Internet
Gateway and a NAT Gateway to it, and creates two route tables: public (the one with direct access
to the Internet) and private (not accessible from the Internet, default route via NAT Gateway).

The default route table is left unmodified and can be used as an isolated route table (access only
inside the VPC itself), e.g., for placing RDS Instances.

A NAT Gateway is placed in one, randomly chosen, public subnet.

As most VPCs contain one or more EKS clusters, the VPC and public subnets are automatically tagged
so EKS can recognise the clusters.

As there are many possible network layouts, no private subnets are created by default, use
``vpc/subnets`` module to add them.

Copyright (c) 2020 Automat-IT


Parameters
==========

``name``
  Base name for the VPC and sub-resources, must be in the "Project-ENV" format. Resource names are
  generated by appending individual identifiers to this - e.g., "Project-ENV-VPC" or
  "Project-ENV-Public-SUBNET-a".

``cidr``
  IPv4 CIDR prefix to associate with the VPC. NB: Though VPC supports more than one range - this
  feature is too rarely used and is not covered by the module.

``public_zones``
  Availability zones names to cover with public subnets. A good default is ``local.zone_names``.

``public_bits``, ``public_base``
  Public subnets prefix width and base number - see Terraform's ``cidrsubnet()`` function docs for
  details.

``tags``, ``vpc_tags``, ``public_tags``
  Extra tags for the resources. "Name" and "Tier" tags are appended to this map.


Outputs
=======

``id``, ``name``
  ID (suitable for "vpc_id" parameter) and name of the VPC

``rt_default``, ``rt_public``, ``rt_private``
  Default, Public and Private VPC route tables, respectively.

``natgw_ip``
  External Elastic IP address attached to the NAT Gateway.

``natgw_subnet``
  The subnet in which NAT Gateway is placed. Useful for placing other resources.

``public_subnets``
  A map of public subnets as a list (``public_subnets.ids``) and them as a map with AZ name as a
  key (``public_subnets.azs``).


Example
=======

Can be used as follows::

  ### VPC: MGMT
  module "vpc" {
    source = "../../modules/vpc/3tier/"

    name = local.basename
    cidr = var.vpc_cidr

    public_zones = local.zone_names
    public_bits  = 8
    public_base  = 0

    tags        = local.base_tags
    vpc_tags    = { "kubernetes.io/cluster/${local.eks_cluster}" = "shared" }
    public_tags = {"kubernetes.io/role/elb" = "1"}
  }


.. vim: set ts=2 sw=2 et tw=98 spell:
