aws ecr get-login-password \
    --region us-east-2 \
| docker login \
    --username AWS \
    --password-stdin 500674654096.dkr.ecr.us-east-2.amazonaws.com

docker build -t 500674654096.dkr.ecr.us-east-2.amazonaws.com/fed-tokenbridge:$1 .