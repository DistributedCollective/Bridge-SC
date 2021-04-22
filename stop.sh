cd "$(dirname "$0")"
docker rm -f `docker ps -qa`
cd -