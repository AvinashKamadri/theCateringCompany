#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
npx prisma@5.17.0 generate --schema=database/schema.prisma
npx prisma@5.17.0 db push --schema=database/schema.prisma --accept-data-loss
