#!/bin/bash
export FED_ENV=$1
export DEPLOY_ENV=$2

cd "$(dirname "$0")"

if [ -z "$FED_ENV" ]
then
        echo "ERROR: please choose the federator env config."
        exit
fi

echo "start fed on $ED_ENV.."
mkdir federator-env/$FED_ENV/db
echo "createing db folder.."

if [ "$DEPLOY_ENV" != "dev" ]
then
        echo "getting fed secret:"
        FED_KEY_NAME=`aws ec2 describe-instances --filters Name=instance-id,Values=$(wget -qO- http://instance-data/latest/meta-data/instance-id) --query Reservations[].Instances[].Tags[].Value --output text`
        FED_KEY=`aws secretsmanager get-secret-value --secret-id $FED_KEY_NAME --region us-east-2 | jq -r .SecretString`
        echo using key named: $FED_KEY_NAME
        cat << EOF > federator-env/$FED_ENV/federator.key
        $FED_KEY
EOF
fi
echo "starting federator please wait..."
nohup docker-compose up > federator.log 2>&1 &



if [ "$DEPLOY_ENV" != "dev" ]
then
        sleep 30
        echo "federator logs: federator.log"
        rm -rf federator-env/$FED_ENV/federator.key
EOF
fi

tail -f federator.log


cd -