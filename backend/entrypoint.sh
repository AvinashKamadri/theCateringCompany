#!/bin/sh
set -e

echo "[entrypoint] Running Prisma migrations..."
npx prisma db push --skip-generate

echo "[entrypoint] Starting NestJS API..."
exec node dist/main
