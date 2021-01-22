#!/usr/bin/env sh
export ANSIBLE_NOCOWS=1

export ENVIRONMENT="$1"
ENV_PATH="../$ENVIRONMENT/ansible"

ansible-playbook -i "$ENV_PATH/hosts" setup-environment.yml --user "root" --extra-vars "@$ENV_PATH/custom-vars.json"
