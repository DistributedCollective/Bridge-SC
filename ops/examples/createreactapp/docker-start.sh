# !/usr/bin/env sh

# Copy custom environment, see: 
# https://www.freecodecamp.org/news/how-to-implement-runtime-environment-variables-with-create-react-app-docker-and-nginx-7f9d42a91d70/

echo "window._env_ = \"$ENVIRONMENT\"" > /var/www/config/env.js;

http-server-spa /var/www index.html 8080