FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
# Network-hardening: npm occasionally fails with ECONNRESET in CI/buildkit.
# Increase fetch retries/timeouts and skip audit/fund during image build.
RUN npm config set fund false \
 && npm config set audit false \
 && npm config set fetch-retries 5 \
 && npm config set fetch-retry-mintimeout 20000 \
 && npm config set fetch-retry-maxtimeout 120000 \
 && npm config set fetch-timeout 600000 \
 && npm ci --no-audit --no-fund

COPY prisma ./prisma
RUN npx prisma generate

COPY . .
RUN npm run build

# ─── Runner ───────────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

# Chromium for Puppeteer PDF generation (contract approvals)
RUN apk add --no-cache chromium

ENV NODE_ENV=production
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/src ./src
COPY --from=builder /app/tsconfig.json ./tsconfig.json
COPY --from=builder /app/nest-cli.json ./nest-cli.json

# Startup: run DB migrations then start the API
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 3001

CMD ["./entrypoint.sh"]
