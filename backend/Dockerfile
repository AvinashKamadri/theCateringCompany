FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

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
ENV ML_ENV=development
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/src ./src

# Startup: run DB migrations then start the API
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 3001

CMD ["./entrypoint.sh"]
