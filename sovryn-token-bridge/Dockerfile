FROM node:14

RUN npm install pm2 -g

COPY ./federator /app/federator
COPY ./abis /app/abis

RUN chown -R node:node /app

USER node
WORKDIR /app/federator

RUN npm install

EXPOSE 30303

CMD [ "npm", "start" ]
# ENTRYPOINT [ "pm2-runtime", "src/main.js" ]