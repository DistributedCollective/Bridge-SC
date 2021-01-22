# Quick Start Guide

This page contains a list of steps you should execute to get everything up and running. If you want to get the commands to be ran or understand the rationale and underlying concepts, please refer to each section.

1. Include ops scripts in your repository.
2. [Hosts setup](remote-setup.md)
   1. Create staging and uat domains.
   2. Add team members ssh keys to grant them access to remote servers
   3. Add on each environment `configs` folder all all the secret files you want to get copied to the server. **Don't forget NOT to push them**
   4. Execute `ops.sh` config server task to setup everything.
3. [CI / CD - Gitlab](gitlab-ci.md)
   1. Prevent merges to `develop` and `master` if CI fails
   2. Create and configure `.gillab-ci.yaml` files for the frontend, the backend and deployments.
   3. Create and configure each `.env` file with environment variables, host names, etc.
   4. Configure the secrets, if any, as Gitlab Variables
4. [Monitoring](monitoring.md#Deploying) the exporters and distributors)
   1. Setup the `prometheus.yml` and `promtail.yml`
   2. Configure proper `docker-overrides.yml`
