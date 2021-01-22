# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## [3.0.0](https://gitlab.com/atixlabs/atix-ops/compare/v1.1.0...v3.0.0) (2020-05-30)


### Features

* Allow docker-compose overrides per environment ([f5d3bb3](https://gitlab.com/atixlabs/atix-ops/commit/f5d3bb3f542540473c704cfb171b3e4cf6e3710c))
* Monitoring integration using Prometheus, Loki and Grafana ([8980857](https://gitlab.com/atixlabs/atix-ops/commit/8980857bc2372f8bdaa6b3bbfee0c04fb7001e95))


### Bug Fixes

* `ops.sh` was broken when no `docker-compose-overrides` were used ([f569b32](https://gitlab.com/atixlabs/atix-ops/commit/f569b32e3646d882b83418859fa26486c16aaed9))
* https only and LE challenge working over TLS ([da9c184](https://gitlab.com/atixlabs/atix-ops/commit/da9c1848bce43f1c84f3cfb78aa7e0eaf03ee367))
* ops.sh and setup-environment.sh to make it work with environments ([4201f3b](https://gitlab.com/atixlabs/atix-ops/commit/4201f3b9eb4c41a9def91250bcf1c959d6f5ef9e))


### Docs

* main README.md split to make it easier to read ([dbf3e87](https://gitlab.com/atixlabs/atix-ops/commit/dbf3e87d00ec190059b0332352852992d4805cfa))
* Quick start guide ([30df2f4](https://gitlab.com/atixlabs/atix-ops/commit/30df2f40e3dd7cf6ddee5d3520f4ba1ead0fd660))
* toc updated ([62e22b5](https://gitlab.com/atixlabs/atix-ops/commit/62e22b5b58e842fd006783c33a52e32ff5f619cc))
* tools being used updated ([87c43bc](https://gitlab.com/atixlabs/atix-ops/commit/87c43bcdcea28e12192d2f9dfbfcd19606d9d58e))

## [2.0.0](https://gitlab.com/atixlabs/atix-ops/compare/v1.1.0...v2.0.0) (2020-05-19)


### ⚠ BREAKING CHANGES

* deploy scripts were simplified

### Features

* Allow docker-compose overrides per environment ([f59f009](https://gitlab.com/atixlabs/atix-ops/commit/f59f009780ab13167b741e30f0d05e9d545a0a77))


### Docs

* main README.md split to make it easier to read ([dbf3e87](https://gitlab.com/atixlabs/atix-ops/commit/dbf3e87d00ec190059b0332352852992d4805cfa))

## [1.1.0](https://gitlab.com/atixlabs/atix-ops/compare/v1.0.0...v1.1.0) (2020-04-25)


### Features

* adds http to https supports. To do so Traefix version was fixed to 2.2 due to API changes ([3240ef2](https://gitlab.com/atixlabs/atix-ops/commit/3240ef24c29392f6dc5a3e55911625afc7326c1e)), closes [#12](https://gitlab.com/atixlabs/atix-ops/issues/12)


### Bug Fixes

* fix the versions that ansible galaxy needs to use ([2bbe546](https://gitlab.com/atixlabs/atix-ops/commit/2bbe546d74571c0ecf5ce3937f74243e41b1efa7)), closes [#13](https://gitlab.com/atixlabs/atix-ops/issues/13)
* fixed maven examples to properly use a fixed version maven docker image ([e0ecdcc](https://gitlab.com/atixlabs/atix-ops/commit/e0ecdcc65cde3526c215eb5f4c6b1f61ec0b2e76)), closes [#7](https://gitlab.com/atixlabs/atix-ops/issues/7)

## 1.0.0 (2020-02-03)


### Features

* atix Ops initial commit ([7e526f0](https://gitlab.com/atixlabs/atix-ops/commit/7e526f0d2bd7642d68d913e6419158b3eb9c398a))
* standard Version added to generate changelog and versions ([0c1a514](https://gitlab.com/atixlabs/atix-ops/commit/0c1a514ec5183825917bbbb876d0b2579c6133ca))


### Docs

* added CONTRIBUTING doc ([0163f18](https://gitlab.com/atixlabs/atix-ops/commit/0163f1838153ca8f1c8f8c28951e8c2da436da17))
* improved README adding sections about GitlabCI configuration ([b8c987b](https://gitlab.com/atixlabs/atix-ops/commit/b8c987bae3825e0ee7c50492e4e451696b2ab47e))
* improved README with an explanation about including atix-ops in a repo ([5b3d2b7](https://gitlab.com/atixlabs/atix-ops/commit/5b3d2b70962e163e20a41a5acf72afa93ce70a5e))
* updated README in order to avoid using 3 DNS records and only use 2 ([b88ac2b](https://gitlab.com/atixlabs/atix-ops/commit/b88ac2b69d4e06aab6690a9b3b5e69b19fe58902))
* updated TODO section ([b202bdf](https://gitlab.com/atixlabs/atix-ops/commit/b202bdf5d701458b548504589b62fb7abf64f910))
