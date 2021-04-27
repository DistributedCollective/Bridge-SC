======================
MODULES: VPC & Subnets
======================

General
=======

These modules are intended to describe network structure for common projects.

Copyright (c) 2020 Automat-IT

Modules
=======

``vpc/isolated``, ``vpc/subnets``
  Basic building blocks: a VPC itself and a set of subnets for each of the availability zones in a
  region.

``vpc/public``
  VPC with a set of public subnets, Internet Gateway, and route tables for public and isolated
  subnets. Built on top of ``vpc/isolated`` module.

``vpc/3tier``
  VPC with 3-tier structure: a set of public subnets, Internet and NAT Gateways, and route tables
  for public, private and isolated subnets. Built on top of ``vpc/public`` module.


Basic Example
=============

Full 3-tier VPC tagged for usage with EKS Cluster with public, private and database subnets
description::

  ### Locals
  locals {
    eks_cluster_name = "${local.basename}-EKS"

    eks_vpc_tags = {"kubernetes.io/cluster/${local.eks_cluster_name}" = "shared"}
  }

  ### VPC: Example
  module "vpc" {
    source = "../../modules/vpc/3tier/"

    name  = local.basename

    cidr  = var.vpc_cidr

    public_zones = local.zone_names
    public_bits  = 4
    public_base  = 0

    tags        = local.base_tags
    vpc_tags    = local.eks_vpc_tags

    # Allow external ELB
    public_tags = {"kubernetes.io/roles/elb" = "1"}
  }

  ### VPC Subnets: Private, internal ELB
  module "private-subnets" {
    source = "../../modules/vpc/subnets/"

    vpc_id = module.vpc.id

    basename = "${local.basename}-Private"

    zones  = local.zone_names
    prefix = var.vpc_cidr
    bits   = 4
    base   = 8

    route_table = module.vpc.rt_private

    tags = merge(local.base_tags, {
      Tier = "Private"
      "kubernetes.io/role/internal-elb" = "1"
    })
  }

  ### VPC Subnets: Database (isolated)
  module "db-subnets" {
    source = "../../modules/vpc/subnets/"

    vpc_id = module.vpc.id

    basename = "${local.basename}-DB"

    zones  = local.zone_names
    prefix = var.vpc_cidr
    bits   = 4
    base   = 12

    route_table = module.vpc.rt_default

    tags = merge(local.base_tags, {
      Tier = "DB"
    })
  }


Details
=======

The modules are modelled on three types of VPCs from our base designs. The goal of these modules
is to provide basic building blocks for most of the basic architectures we deal with, and being
reasonably flexible and manageable.

As all our VPC cover multiple availability zones in an Amazon region, a common module,
``vpc/subnets``, is provided to create a set of consecutive subnets of the specified width,
starting from specified base. Terraform's ``cidrsubnet()`` function is used to compute the IP
ranges.

Isolated VPC provided by ``vpc/isolated`` module, though quite rare, is a convenient base for any
type of VPC - it doesn't contain anything but is tagged according to our standard. The default
route table is intended to contain no external routes, just the route to the VPC itself and,
optionally, routes to peering connection, transit gateway attachment, gateway endpoint, etc. An
example of isolated VPC is a so-called "Database VPC" which contains only a set of isolated
networks in which an RDS instance runs, and connected to other regions through peering or Transit
Gateway feature. Other types of VPCs can be built on top of it, maintaining the common interface.

Public VPC provided by ``vpc/public`` module is based upon the Isolated VPC. It contains a set of
subnets, which are attached to a route table with default route via an Internet Gateway. The
subnets and both "public" and "default" route tables are returned as outputs, along with VPC ID
and name.

The most complicated VPC is 3-tier one provided by ``vpc/3tier`` module. It is based on a Public
VPC and, in addition to the set of public subnets, creates a NAT Gateway in one of them - chosen
randomly, and a "private" route table with a default route through it.

Note that no non-public subnets are provided by any of these modules - the number of "tiers"
actually matches not a number of different subnet classes but the number of different *route
tables* provided.

Tagging
-------

As most of 2-tier and 3-tier VPCs contain an EKS Cluster - there are three parameters which
influence the tags assigned to different resources.

The most basic one, ``tags``, is a map of extra tags to be assigned to *every* resource created by
the modules. A good default is ``local.base_tags`` as defined by ``common.tf``.

The second parameter, ``vpc_tags``, is a map of tags to be assigned to the VPC itself **and** the
public subnets. The intended use is to add "kubernetes.io/cluster/cluster_name=shared" tag to be
added to them to indicate that they can be used by EKS Cluster, but there may be other uses for
this feature. Though it is relatively harmless to have EKS tags on, e.g., routing tables, the
parameter is there to prevent any unintended side-effects - and, to some extent, to avoid noise.

The third parameter, ``public_tags``, is a map of tags to be assigned specifically to the public
subnets. The intended use is to add "kubernetes.io/role/elb=1" tag required for ALB Ingress.


.. vim: set ts=2 sw=2 et tw=98 spell:
