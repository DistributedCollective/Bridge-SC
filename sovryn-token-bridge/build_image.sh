version=$1
docker build -t sovryn/fed-tokenbridge:$version .
docker push sovryn/fed-tokenbridge:$version
