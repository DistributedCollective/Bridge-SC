FROM node:22-bookworm@sha256:0e5f906573693feaa1e21057ebdcfdb5bd5021f050b2dc7c9deceb629c7da2a8
WORKDIR /opt/lab/app/federator
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY app/ /opt/lab/app/
COPY worker.cjs fork_lab.py /opt/lab/
COPY anvil /usr/local/bin/anvil
RUN node -e "require('sodium-secretstream'); require('ataraxia-tcp'); console.log('Native transport loads')"
