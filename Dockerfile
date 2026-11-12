# tab-harvest MCP server — Node build with python3/yt-dlp available to the server process
FROM node:22-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages --no-cache-dir yt-dlp

WORKDIR /app

COPY mcp-server/package.json ./
RUN npm install

COPY mcp-server/ ./
RUN npm run build

ENV PORT=3000
EXPOSE 3000

CMD ["npm", "start"]
