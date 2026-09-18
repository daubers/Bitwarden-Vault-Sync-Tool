FROM mcr.microsoft.com/playwright:v1.47.0-jammy

RUN npm install -g @bitwarden/cli

WORKDIR /seed
COPY package.json .
RUN npm install
COPY seed.js .

CMD ["node", "seed.js"]
