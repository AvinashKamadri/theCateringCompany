FROM node:20-slim AS builder

WORKDIR /app

# Chromium for Puppeteer PDF generation
RUN apt-get update && apt-get install -y chromium --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Build context is repo root (set in docker-compose)
COPY workers/package*.json ./
RUN npm ci

# Prisma schema lives in backend — copy it for client generation
COPY backend/prisma/schema.prisma ./prisma/
RUN npx prisma generate

COPY workers/src ./src
COPY workers/tsconfig.json ./tsconfig.json
RUN npm run build

# ─── Runner ───────────────────────────────────────────────────────────────────
FROM node:20-slim AS runner

RUN apt-get update && apt-get install -y chromium --no-install-recommends && rm -rf /var/lib/apt/lists/*

ENV NODE_ENV=production
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/package*.json ./

CMD ["node", "dist/index.js"]
