# Deployment Guide

**Architecture**
| Service | Host | Notes |
|---------|------|-------|
| Frontend (Next.js) | Vercel | auto-deploy from git |
| Backend (NestJS) | GCP VM | Docker Compose |
| Workers (BullMQ) | GCP VM | Docker Compose |
| ML Agent (FastAPI) | GCP VM | Docker Compose |
| Postgres | GCP VM | Docker container, data in volume |
| Redis | GCP VM | Docker container |

---

## Part 1 — GCP VM (Backend)

### 1.1 Create a VM on GCP

1. Go to **Compute Engine → VM Instances → Create Instance**
2. Recommended specs:
   - Machine type: `e2-standard-2` (2 vCPU, 8 GB) or `e2-medium` (1 vCPU, 4 GB)
   - OS: Ubuntu 22.04 LTS
   - Boot disk: 30 GB SSD
3. Under **Firewall**: check **Allow HTTP** and **Allow HTTPS**
4. Under **Networking → Network tags** add tag: `catering-backend`
5. Click Create, wait for the VM to start

### 1.2 Open Firewall Ports

In GCP Console → **VPC Network → Firewall → Create Firewall Rule**:

| Rule name | Direction | Targets | Protocols/ports |
|-----------|-----------|---------|-----------------|
| `allow-backend` | Ingress | Tag: `catering-backend` | tcp: 3001 |
| `allow-ml-agent` | Ingress | Tag: `catering-backend` | tcp: 8000 |

> Port 3000 (frontend) is NOT needed — frontend is on Vercel.

### 1.3 SSH into the VM

```bash
# From GCP Console → VM Instances → click "SSH"
# Or via gcloud:
gcloud compute ssh INSTANCE_NAME --zone=YOUR_ZONE
```

### 1.4 Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker compose version   # should print v2.x
```

### 1.5 Clone the Repo

```bash
git clone <your-repo-url> app
cd app
git checkout deploy
```

### 1.6 Create the Production Env File

```bash
cp .env.production.example .env.production
nano .env.production
```

Fill in every `FILL_IN` value. Key ones:

```bash
# Generate JWT secrets:
openssl rand -base64 48   # → JWT_SECRET
openssl rand -base64 48   # → JWT_REFRESH_SECRET

# Pick a strong Postgres password for POSTGRES_PASSWORD
# Paste your OpenAI API key for OPENAI_API_KEY
# CORS_ORIGIN = your Vercel URL (get this after Part 2)
```

### 1.7 Start All Backend Services

```bash
docker compose -f docker-compose.gcp.yml --env-file .env.production up -d --build
```

This starts: **postgres, redis, backend, workers, ml-agent**

First run takes ~5-10 minutes (builds all images). The backend automatically runs `prisma migrate deploy` on startup.

### 1.8 Verify

```bash
docker compose -f docker-compose.gcp.yml ps
# All 5 services should show "Up" or "healthy"

# Check logs
docker compose -f docker-compose.gcp.yml logs backend --tail=30
docker compose -f docker-compose.gcp.yml logs ml-agent --tail=30
```

Test from your local machine:
```
http://VM_EXTERNAL_IP:3001/api        → backend
http://VM_EXTERNAL_IP:8000/health     → ml-agent
```

Get your VM's external IP from GCP Console → Compute Engine → VM Instances.

---

## Part 2 — Vercel (Frontend)

### 2.1 Push the deploy branch

```bash
git push origin deploy
```

### 2.2 Import on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repo
3. Set **Root Directory** to `frontend`
4. Framework is auto-detected as Next.js

### 2.3 Set Environment Variables in Vercel

In Vercel → Project Settings → **Environment Variables**, add:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `http://VM_EXTERNAL_IP:3001` |
| `NEXT_PUBLIC_ML_API_URL` | `http://VM_EXTERNAL_IP:8000` |
| `NEXT_PUBLIC_WS_URL` | `ws://VM_EXTERNAL_IP:3001` |

> Replace `VM_EXTERNAL_IP` with your GCP VM's external IP.
> Once you have a domain + SSL, change these to `https://` and `wss://`.

### 2.4 Deploy

Click **Deploy**. Vercel builds and deploys automatically.

After deploy, copy your Vercel URL (e.g. `https://the-catering-company.vercel.app`).

### 2.5 Update CORS on the GCP VM

Edit `.env.production` on the VM:
```bash
CORS_ORIGIN=https://the-catering-company.vercel.app
```

Restart the backend:
```bash
docker compose -f docker-compose.gcp.yml --env-file .env.production up -d backend
```

---

## Database

The database runs as a **Docker container on the GCP VM** (`pgdata` volume).

**Backup:**
```bash
docker compose -f docker-compose.gcp.yml exec postgres \
  pg_dump -U cateringco cateringco_prod > backup_$(date +%Y%m%d).sql
```

**Restore:**
```bash
cat backup_YYYYMMDD.sql | docker compose -f docker-compose.gcp.yml exec -T postgres \
  psql -U cateringco cateringco_prod
```

**Migrations** run automatically every time the backend container starts (`prisma migrate deploy` in entrypoint.sh).

> Later you can migrate to **Cloud SQL** (GCP managed Postgres) by changing
> `DATABASE_URL` in `.env.production` to the Cloud SQL connection string
> and removing the `postgres` service from `docker-compose.gcp.yml`.

---

## Deploying Updates

```bash
# On the GCP VM:
cd app
git pull origin deploy
docker compose -f docker-compose.gcp.yml --env-file .env.production up -d --build
```

Vercel auto-deploys when you push to the `deploy` branch (if you connect the branch in Vercel settings).

---

## Optional: Custom Domain + HTTPS

1. Point your domain's DNS to the GCP VM's external IP (A record)
2. SSH into the VM, install Nginx + Certbot:
   ```bash
   sudo apt install nginx certbot python3-certbot-nginx -y
   ```
3. Create Nginx config to proxy ports 3001 and 8000 behind your domain
4. Run `sudo certbot --nginx` to get free SSL
5. Update `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL` in Vercel to `https://` URLs
6. Update `CORS_ORIGIN` on the VM to your frontend domain
7. Redeploy both

---

## Quick Reference

| What | Command |
|------|---------|
| Start all services | `docker compose -f docker-compose.gcp.yml --env-file .env.production up -d --build` |
| Stop all | `docker compose -f docker-compose.gcp.yml down` |
| View logs | `docker compose -f docker-compose.gcp.yml logs -f SERVICE` |
| Restart one service | `docker compose -f docker-compose.gcp.yml restart backend` |
| DB backup | see Database section above |
| Check service status | `docker compose -f docker-compose.gcp.yml ps` |
