1. run "docker login" with sovryn account cred 
2. run the build_image.sh script from "sovryn-token-bridge/build_image.sh" and give it a version as parameter
3. change image entry at the 2 docker-compose files with the new version
  docker-compose-prod.yml
  docker-compose-test.yml
4. push docker-compose file changes to master
