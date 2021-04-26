export FED_ENV=$1

aws ecr get-login-password \
    --region us-east-2 \
| docker login \
    --username AWS \
    --password-stdin 500674654096.dkr.ecr.us-east-2.amazonaws.com
    
if [ -z "$FED_ENV" ]
then
        echo "ERROR: please choose the federator env config."
        exit
fi

echo "start fed on $ED_ENV.."
mkdir -p /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/db
echo "createing db folder.."
echo "getting fed secret:"
FED_KEY_NAME=`aws ec2 describe-instances --filters Name=instance-id,Values=$(wget -qO- http://instance-data/latest/meta-data/instance-id
) --query Reservations[].Instances[].Tags[].Value --output text`
FED_KEY=`aws secretsmanager get-secret-value --secret-id $FED_KEY_NAME --region us-east-2 | jq -r .SecretString`
echo using key named: $FED_KEY_NAME
cat << EOF > /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/federator.key
$FED_KEY
EOF
echo "starting federator please wait..."
nohup docker-compose up > federator.log 2>$1 &
sleep 30
echo "federator logs: /home/ubuntu/Bridge-SC/federator.log"
rm -rf /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/federator.key
tail -f /home/ubuntu/Bridge-SC/federator.log