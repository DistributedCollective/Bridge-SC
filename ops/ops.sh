#! /usr/bin/env bash

CMD="$1"
ENVIRONMENT="$2"
EXTRA_PARAMS="$3"

OPS_PATH=`pwd`
DOCKER_PATH="$(pwd)/docker"

get_overrides() {
    OVERRIDES="./$1/docker/docker-compose-overrides.yml"
    if [[ -e "$OVERRIDES" ]]; then
        echo "-f $(readlink -f $OVERRIDES)"
    fi
}

load_env() {
    export ENVIRONMENT=$1

    # Load env vars
    ENV_FILE="$OPS_PATH/$ENVIRONMENT/docker/.env"

    if [[ -e "$ENV_FILE" ]]; then
        echo "> Loading environment configs from $ENV_FILE"
        source "$ENV_FILE"
    else
        echo "> No env file found for path $ENV_FILE"
    fi
}

execute_docker_command() {
    export ENVRIONMENT=$1
    load_env "$1"
    cd "$DOCKER_PATH"
    
    OVERRIDES="../$1/docker/docker-compose-overrides.yml"
    if [[ -e "$OVERRIDES" ]]; then
        if [[ -z "$3" ]]; then
            docker-compose -p "$PROJECT" -f docker-compose-base.yml -f "$(readlink -f $OVERRIDES)" $2
        else
            docker-compose -p "$PROJECT" -f docker-compose-base.yml -f "$(readlink -f $OVERRIDES)" $2 "$3"
        fi
    else
        if [[ -z "$3" ]]; then
            docker-compose -p "$PROJECT" -f docker-compose-base.yml $2
        else
            docker-compose -p "$PROJECT" -f docker-compose-base.yml $2 "$3"
        fi
    fi 
}

deploy() {

    # Refresh Docker Images
    execute_docker_command $1 pull "$2"
    # Start the container
    execute_docker_command $1 'up -d' "$2"
}

destroy() {
    execute_docker_command $1 "down"
}

restart() {
    execute_docker_command $1 "restart"
}

fix_mup_network() {
    load_env "$1"    

    docker network connect --alias hitcoins-front hitcoins-uat_monitoring-network hitcoins-front
    docker restart hitcoins-front
}

case $CMD in
    --config-server)
    cd ./ansible
    ./install-roles.sh && ./setup-environment.sh "$ENVIRONMENT" 
    ;;
    --deploy)
        deploy "$ENVIRONMENT" "$EXTRA_PARAMS"
    ;;
    --destroy)
        destroy "$ENVIRONMENT"
    ;;
    --restart)
        restart "$ENVIRONMENT"
    ;;
    *) # unknown option
    echo 'Valid commands'
    echo '  --config-server $environment'
    echo '  --deploy $environment'
    echo '  --destroy $environment'
    echo '  --restart $environment'
    ;;
esac
