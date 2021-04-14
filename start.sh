export FED_ENV=$1

if [ -z "$FED_ENV" ]
then 
	echo "ERROR: please choose the federator env config."
	exit
fi

FED_KEY_NAME=`aws ec2 describe-instances --filters Name=instance-id,Values=$(wget -qO- http://instance-data/latest/meta-data/instance-id) --query Reservations[].Instances[].Tags[].Value --output text`
FED_KEY=`aws secretsmanager get-secret-value --secret-id $FED_KEY_NAME --region us-east-2 | jq -r .SecretString`
cat << EOF > /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/federator.key
$FED_KEY
EOF

nohup docker-compose up > federator.log 2>$1 &
rm -rf /home/ubuntu/Bridge-SC/federator-env/$FED_ENV/federator.key
