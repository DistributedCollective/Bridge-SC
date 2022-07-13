with github actions
1. go to docker-compose-prod.yml, docker-compose-test.yml under the image property you should incremenet image version by 0.1 points
2. commit and create tag with the same version you have specifified in the docker-compose files
3. push the commit and tag. github action would be trigger and push the new image to sovryn docker account

* create tag: ```git tag 8.5```

* push tag: ```git push origin 8.5```



locally
1. run "docker login" with sovryn account cred 
2. run the build_image.sh script from "sovryn-token-bridge/build_image.sh" and give it a version as parameter
3. change image entry at the 2 docker-compose files with the new version
  docker-compose-prod.yml
  docker-compose-test.yml
4. push docker-compose file changes to master
