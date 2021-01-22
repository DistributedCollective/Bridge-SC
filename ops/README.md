# Atix Ops

This repository proposes a standard base setup that can be used to launch and deploy dev, staging, uat and even production environments. It might be obvious but it's worth mentioning that it will depend on the architecture of the system to be deployed and the non-functional requirements the project has (amount of concurrent users that need to be served, the amount of data that needs to be processed or stored, etc).

This is a first step towards a more complex CI/CD workflow using multiple servers with green/blue deployments capabilities (k8s based with ArgoCD maybe) and a [Beyond Corp](https://en.wikipedia.org/wiki/BeyondCorp) zero trust setup. Taking this to the next level will depend on the success of this approach and the need of a more advanced solution. You can read more about our [roadmap here](#Roadmap).

The tools, scripts and configs that can be found here will help to:

- Setup a remote environment (i.e. configure a linux VPS instance with all the required runtime tools) following Atix Labs [security best practices](https://awesome.atixlabs.com).
- Deploy on a single server a set of machines using docker-compose that will connect each other to provide backend, frontend and monitoring services.
- Setup monitoring tools.

## TOC

<!-- toc -->

- [Rationale](#rationale)
- [Roadmap](#roadmap)
- [Workflow](#workflow)
- [Directory Structure](#directory-structure)
- [How to include Ops scripts in your project?](#how-to-include-ops-scripts-in-your-project)
- [Quick start Guide](#quick-start-guide)
- [Gitlab CI](#gitlab-ci)
- [Remote Setup](#remote-setup)
- [Secrets](#secrets)
- [Deploying the Apps](#deploying-the-apps)
- [TO DO](#to-do)
- [Built With](#built-with)

<!-- tocstop -->

## Rationale

We must deliver top quality and reliable solutions that meets each project user needs. In order to do so we need to be able to deploy and test our work as soon as possible to gather feedback from QC and the project stakeholders.

To do so, the following requirements must be met:

- Not let anyone merge a pull request with failing tests to any stable branch (aka. master, develop).
- Be able to easily (i.e. automatically or with _just a click_) deploy to staging, UAT and production environments.
- Minimize the infrastructure (ops) work and hassle when configuring before mentioned environments.
- Easily grant (and revoke) access to our servers in order to troubleshoot any problems we might be experiencing (production, uat or staging).
- Monitor our apps system load and application related metrics.

## Roadmap

1. [x] Get rid of Jenkins for CI tasks and start using GitlabCI:
2. [x] Create our own private Docker Registry to host our images and move all the projects to a docker based deployment schema.
3. [x] Create a unified deployment schema and create repository to hold common scripts and configuration examples.
4. [ ] Improve secrets management.
5. [ ] Replace our CD solution implement a green/blue deploy schema with QC team promotions using tools like [ArgoCD](https://argoproj.github.io/argo-cd/) or GitlabCI based.
6. [ ] Beyond corp solution to allow team members to easily access to the servers(something like gravitational teleport).

## Workflow

The proposed workflow utilized Gitlab CI/CD features to test, package and deploy the apps. The workflow is the following:

1. People work and push their code to their own `feature/xxxx` branched.
2. Once they create a Merge Request, code is linted and tests are checked. If any error the merge will be blocked.
3. If everything is ok and the code is merged to `develop` the code will be packaged using docker (i.e. a docker image will be created) and pushed to Atix Docker Registry.
4. If a deploy needs to be made, devs need to update a deployment configuration file specifying which images are going to be deployed.
5. Once that's done, we will use Gitlab's UI to invoke such deploys.

## Directory Structure

```
├── ansible # Directory containing common Ansible files
│   ├── gitlabci.pub # GitlabCI public key that will be used to deploy using ssh
│   ├── install-roles.sh # Script to install playbook requirements
│   ├── requirements.yml # Playbook dependencies
│   ├── setup-environment.sh # Script to invoke ansible
│   └── setup-environment.yml # Setup environment playbook
├── docker # Directory containing common Docker files
│   └── docker-compose-base.yml # Deployment definition
├── ops.sh # Main script to be used to deploy
├── examples # Example project configuration files
└── $ENVIRONMENT # One for each environment i.e. staging, uat, production
    ├── ansible # Environment deployment config
    │   ├── custom-vars.json # SSH keys that will grant access to that environment over ssh
    │   ├── hosts # Environment domain name or ip
    │   └── ssh-keys # Keys that were configured in custom-vars.json
    │       ├── key1.pub
    │       └── key2.pub
    ├── configs # Directory with configs that will be copied to the host
    └── docker # Docker environment config
        ├── .env # Environment variables to be used in docker-compose
        └── docker-compose-overrides.yml # Custom docker containers for this environment
```

## How to include Ops scripts in your project?

We want to be able to:

- Include changes from `atix-ops`.
- Be able to edit some files and push it to our project repositories.
- Pull changes (fixes, improvements) made in `atix-ops` to our project.

We suggest using `git subtree`. As explained [here](https://stackoverflow.com/a/31770147) subtree fits best that use case:

> subtree is more like a system-based development, where your all repo contains everything at once, and you can modify any part.

A nice tutorial can be found [here](https://www.atlassian.com/git/tutorials/git-subtree) and a more detailed explanation [here](https://medium.com/@porteneuve/mastering-git-subtrees-943d29a798ec)

Steps to include ops in **your project**:

1. Move to the project directory:

```
cd myProject
```

2. Add this repository as a remote:

```
git remote add atix-ops git@gitlab.com:atixlabs/atix-ops.git
```

3. Initialize the subtree by grabbing `atix-ops` master and pulling it into `/ops` directory

```
git subtree add --prefix ops atix-ops master --squash
```

4. A new folder named `./ops` should have been created with `atix-ops` master contents and a commit showing that. For example:

```
commit f40bf124c49bbd53ae7f5d6f1c076e21cd4b4742
Merge: d6f5b6b c8e5fce
Author: Alan Verbner
Date:   Thu Jan 30 13:44:07 2020 -0300

    Merge commit 'c8e5fcef7f2c0a9a025ac1da71984aafce1c68e8' as 'ops'
```

5. You can now update files in `./ops` directory as you need (read steps below to see which ones are you supposed to edit).

6. Push those changes to your repo as usual.

```
git add .
git commit -m "updated ops files in order to ..."
git push origin $your_branch
```

7. If a new update has been pushed to `atix-ops` master, you can download the changes by doing:

```
git fetch atix-ops master # update the reference
git subtree pull --prefix ops aix-ops master --squash # pull the changes into our repo
```

## Quick start Guide

See the [Quick Start Guide](./docs/quick-start-guide.md) to get everything up and running.

## Gitlab CI

See [Gitlab CI](./docs/gitlab-ci.md) for CI configuration instructions.

## Remote Setup

See [Remote Setup](./docs/remote-setup.md).

## Secrets

See [Secrets](./docs/secrets.md).

## Deploying the Apps

See [Deploying the Apps](./docs/deploying-the-apps.md).

## TO DO

The following tasks are not yet included in this process:

- [ ] Documentation improvements:
  - Better diagrams and explanations
  - Link this doc to awesome atix
- Create a set of GitlabCI pipeline examples to be used as starting point
  - [x] Create React App Frontend
  - [ ] NextJs app
  - [ ] NodeJs Backend
  - [x] Maven Based Spring boot app
- [ ] Improve GitlabCi pipelines to follow the recommendations mentioned [here](https://medium.com/@ryzmen/gitlab-fast-pipelines-stages-jobs-c51c829b9aa1).
- [ ] Introduce a backup tool and execution steps to save in a separate server:
  - DB (Postgres and Mongo to start with)
  - FS
  - S3 stored files

## Built With

- [Ansible](https://www.ansible.com/) - The automation tool.
- [Docker](https://www.docker.com) - Container Service.
- [Docker-Compose](https://docs.docker.com/compose/) - Single machine containers orchestration.
- [Trafeik](https://containo.us/traefik/) - Reverse proxy with TLS and docker support.
- [Cadvisor](https://github.com/google/cadvisor) - Docker Monitoring tool.
- [Prometheus](https://prometheus.io/) - Monitoring and Metrics aggregation system
- [Loki](https://grafana.com/oss/loki/) - Logs aggregation
- [Grafana](https://grafana.com/) - Monitoring and Alerting
