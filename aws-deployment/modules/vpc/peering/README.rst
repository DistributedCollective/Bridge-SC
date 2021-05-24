===================
MODULE: VPC Peering
===================

General
=======

This module creates a peering connection between two VPCs.

Copyright (c) 2020 Automat-IT


Providers
=========

The module requires two AWS providers to be passed explicitly: ``aws.local`` for local and
``aws.peer`` for remote side. This allows to use the module cross-region and (potentially)
cross-account, without introducing any complicated or unclear configuration.


Parameters
==========

``name``, ``tags``
  The name of the peering connection and tags to assign to it.


``local_region``, ``local_vpc_id``, ``local_vpc_cidr``
  Local VPC parameters: region, ID and CIDR (used for routing)

``peer_region``, ``peer_vpc_id``, ``peer_vpc_cidr``
  Peer VPC parameters: region, ID and CIDR (used for routing)

``local_route_tables``, ``peer_route_tables``
  List of route tables in the local and peer VPCs to install a route.


Outputs
=======

``pcx_id``
  ID of the VPC peering connection


Common use case
===============

In our common network design pattern the Management VPC is peered with all the other VPCs like
this::

    +-----------------------+
    | MGMT VPC              |
    |                       |            +-----------+
    |  +----------------+   | <========> | STAGE VPC |
    |  | OpenVPN Server |   |            +-----------+
    |  +----------------+   | 
    |                       |            +----------+
    |                       | <========> | PROD VPC |
    |                       |            +----------+
    +-----------------------+

This allows using VPN in the Management VPC as a infrastructure entry point, disallowing other
VPCs to communicate directly with each other.

This module can be used to simplify peering configuration.


Note on routing
---------------

Management VPC usually contains public and private subnets but in some cases may also have a
database/isolated subnets. As most infrastructure there needs to be accessible from peered VPCs
resides either in public (e.g., VPN server or bastion) or private (e.g., Jenkins or Nexus server)
subnets but *not* the database ones - it is not recommended to install routes to peered VPCs into
the default Management VPC route table.

However all three kinds of routing tables in the peered VPCs must have routes to the Management
VPC.

Please note that only a single-hop routing over peering connections: so you cannot add routes from
one peered VPC through the Management VPC to another peered VPC, or use VPN without NAT'ing the
VPN Clients to VPN server internal IP.


Examples
========

Peering with Management VPC in the same region::

  ### VPC Peering: MGMT VPC
  module "mgmt-peering" {
    source = "../../modules/vpc/peering/"

    # Pass local and peer region providers
    providers = {
      aws.local = aws
      aws.peer  = aws
    }

    # Local VPC Info
    local_region   = var.aws_region
    local_vpc_id   = module.vpc.id
    local_vpc_cidr = var.vpc_cidr

    local_route_tables = [
      module.vpc.rt_default,
      module.vpc.rt_public,
      module.vpc.rt_private,
    ]

    # Peer VPC Info
    peer_region   = var.aws_region
    peer_vpc_id   = local.mgmt_vpc.id
    peer_vpc_cidr = local.mgmt_vpc.cidr

    peer_route_tables = [
      local.mgmt_vpc.rt_public,
      local.mgmt_vpc.rt_private,
    ]

    # Naming and Tagging
    name = "${local.basename}-MGMT"
    tags = local.base_tags
  }


Peering with Management VPC in a *different* region::

  ### VPC Peering: MGMT VPC
  # Provider for MGMT Region
  provider "aws" {
    alias  = "mgmt"
    region = var.tfstate_region
  }

  module "mgmt-peering" {
    source = "../../modules/vpc/peering/"

    # Pass local and peer region providers
    providers = {
      aws.local = aws
      aws.peer  = aws.mgmt
    }

    # Local VPC Info
    local_region   = var.aws_region
    local_vpc_id   = module.vpc.id
    local_vpc_cidr = var.vpc_cidr

    local_route_tables = [
      module.vpc.rt_default,
      module.vpc.rt_public,
      module.vpc.rt_private,
    ]

    # Peer VPC Info
    peer_region   = var.tfstate_region
    peer_vpc_id   = local.mgmt_vpc.id
    peer_vpc_cidr = local.mgmt_vpc.cidr

    peer_route_tables = [
      local.mgmt_vpc.rt_public,
      local.mgmt_vpc.rt_private,
    ]

    # Naming and Tagging
    name = "${local.basename}-MGMT"
    tags = local.base_tags
  }


Notes
=====

``local_route_tables`` and ``peer_route_tables`` are optional: if you prefer to install routes
outside of the module you can skip passing it. If ``peer_route_tables`` is not passed, you can
also skip passing ``local_vpc_cidr`` parameter as well, and similarly not passing
``local_route_tables`` makes ``peer_vpc_cidr`` parameter unnecessary. So, the minimal module use
case - without installing mutual routing - is as follows::

  ### VPC Peering: MGMT VPC
  module "mgmt-peering" {
    source = "../../modules/vpc/peering/"

    # Pass local and peer region providers
    providers = {
      aws.local = aws
      aws.peer  = aws
    }

    # Local VPC Info
    local_region   = var.aws_region
    local_vpc_id   = module.vpc.id

    # Peer VPC Info
    peer_region   = var.aws_region
    peer_vpc_id   = local.mgmt_vpc.id

    # Naming and Tagging
    name = "${local.basename}-MGMT"
    tags = local.base_tags
  }


.. vim: set ts=2 sw=2 et tw=98 spell:
