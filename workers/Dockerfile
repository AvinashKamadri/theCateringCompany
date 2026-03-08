FROM node:20-slim AS builder

WORKDIR /app

# Install Chromium for Puppeteer
RUN apt-get update && apt-get install -y chromium --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci

# Copy Prisma schema from backend
COPY ../backend/prisma/schema.prisma ./prisma/
RUN npx prisma generate

COPY . .
RUN npm run build

FROM node:20-slim AS runner

# Install Chromium
RUN apt-get update && apt-get install -y chromium --no-install-recommends && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/prisma ./prisma

CMD ["node", "dist/index.js"]
