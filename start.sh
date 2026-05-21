export FED_ENV=$1
export FED_ID=$2
# export DATADOG_API_KEY=$3


# Error out early if there's any error in the script.
# Otherwise the errors can get uncaught and this wastes development time.
set -e

load_aws_secret_if_unset() {
        ENV_NAME="$1"
        DEFAULT_SECRET_ID="$2"
        eval CURRENT_VALUE="\${$ENV_NAME:-}"
        if [ -n "$CURRENT_VALUE" ]
        then
                return
        fi

        eval SECRET_ID_OVERRIDE="\${${ENV_NAME}_SECRET_ID:-}"
        SECRET_ID="${SECRET_ID_OVERRIDE:-$DEFAULT_SECRET_ID}"

        echo "loading $ENV_NAME from AWS Secrets Manager secret: $SECRET_ID"
        SECRET_STRING=`aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region us-east-2 | jq -r .SecretString`
        SECRET_VALUE=`printf '%s' "$SECRET_STRING" | jq -r --arg key "$ENV_NAME" 'try (fromjson | .[$key] // empty) catch empty'`
        if [ -z "$SECRET_VALUE" ]
        then
                SECRET_VALUE="$SECRET_STRING"
        fi

        export "$ENV_NAME=$SECRET_VALUE"
}

if [ -z "$FED_ENV" ]
then
        echo "ERROR: please choose the federator env config as first cmd arg."
        exit
fi

if [ -z "$FED_ID" ]
then
        echo "ERROR: please provide uniqe id for this federator as second cmd arg."
        exit
fi

# if [ -z "$DATADOG_API_KEY" ]
# then
#         echo "ERROR: please provide datadog api key."
#         exit
# fi

./stop.sh
./reset.sh

echo "Enter datadog-api-key:"
read DATADOG_API_KEY
# echo "Enter pm2-secret-key:"
# read PM2_SECRET_KEY_VAL
export DATADOG_API_KEY=$DATADOG_API_KEY
# export PM2_SECRET_KEY=$PM2_SECRET_KEY_VAL
rm -rf /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/telegram.key

echo "Enter telegram key:"
read TELEGRAM_KEY
echo "$TELEGRAM_KEY" > /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/telegram.key

sed -i 's/federatorInstanceId_replace_this/'"$FED_ID-$FED_ENV"'/g' /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/config.js

echo "Enter Federator public address:"
read FED_ADDRESS

sed -i 's/federatorAddress_replace_this/'"$FED_ADDRESS"'/g' /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/config.js

echo "starting federator on $FED_ENV.. this should take 90 sec, please wait"
mkdir -p /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/db
echo "createing db folder.."
echo "getting fed secret:"
FED_KEY_NAME=`aws ec2 describe-instances --filters Name=instance-id,Values=$(wget -qO- http://instance-data/latest/meta-data/instance-id
) --query "Reservations[].Instances[].Tags[?Key == 'Name'].Value" --output text`
FED_KEY=`aws secretsmanager get-secret-value --secret-id $FED_KEY_NAME --region us-east-2 | jq -r .SecretString`
echo using key named: $FED_KEY_NAME
cat << EOF > /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/federator.key
$FED_KEY
EOF

if [ "$FED_ENV" = "mainnet-BSC-RSK" ]
then
        load_aws_secret_if_unset NODEREAL_BSC_FEDERATOR_API NODEREAL_BSC_FEDERATOR_API
fi

if [ "$FED_ENV" = "mainnet-ETH-RSK" ]
then
        load_aws_secret_if_unset NODEREAL_ETH_FEDERATOR_API NODEREAL_ETH_FEDERATOR_API
fi

echo "starting federator please wait... this takes"
nohup 2>&1 docker-compose -f docker-compose-prod.yml up > federator.log  &
sleep 90
echo "federator logs: /home/ubuntu/Bridge-SC/federator.log"
rm -rf /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/federator.key
tail -f /home/ubuntu/Bridge-SC/federator.log
