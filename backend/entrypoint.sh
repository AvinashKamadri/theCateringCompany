#!/bin/sh
set -e

echo "[entrypoint] Running Prisma migrations..."
npx prisma migrate deploy

echo "[entrypoint] Starting NestJS API..."
exec node dist/main
