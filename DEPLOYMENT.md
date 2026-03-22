# Deployment Guide

**Architecture**
| Service | Host | Notes |
|---------|------|-------|
| Frontend (Next.js) | Vercel | auto-deploy from git |
| Backend (NestJS) | EC2 — Docker Compose | |
| Workers (BullMQ) | EC2 — Docker Compose | |
| ML Agent (FastAPI) | EC2 — Docker Compose | |
| Postgres | AWS RDS | managed, separate from EC2 |
| Redis | EC2 — Docker container | |
| File Storage | AWS S3 | uploads, PDFs |

---

## Part 1 — AWS RDS (Postgres)

### 1.1 Create RDS Instance

1. Go to **AWS Console → RDS → Create database**
2. Settings:
   - Engine: **PostgreSQL 16**
   - Template: **Free tier** (or Production)
   - DB instance identifier: `cateringco-prod`
   - Master username: `cateringco`
   - Master password: pick a strong password, save it
   - DB instance class: `db.t3.micro` (free tier)
   - Storage: 20 GB gp2
   - **Public access: No** (EC2 will connect privately)
3. Under **Connectivity**:
   - VPC: default (must be same VPC as your EC2)
   - Create a new security group: `rds-cateringco`
4. Click **Create database** — takes ~5 minutes

### 1.2 Allow EC2 to Connect to RDS

1. Go to **RDS → your database → Connectivity → Security groups → `rds-cateringco`**
2. Edit inbound rules → Add rule:
   - Type: **PostgreSQL** (port 5432)
   - Source: the security group of your EC2 instance (add this after creating EC2)

### 1.3 Get the RDS Endpoint

From RDS Console → your database → **Endpoint**. Looks like:
```
cateringco-prod.xxxxxxxxxxxx.us-east-1.rds.amazonaws.com
```
Save this — you'll use it as `DATABASE_URL`.

---

## Part 2 — AWS S3 (Storage)

### 2.1 Create S3 Bucket

1. Go to **AWS Console → S3 → Create bucket**
2. Settings:
   - Bucket name: `catering-uploads` (must be globally unique — add your name e.g. `catering-uploads-avinash`)
   - Region: same as your EC2 (e.g. `us-east-1`)
   - Block all public access: **ON** (uploads are private, served via signed URLs)
3. Click **Create bucket**

### 2.2 Create IAM User for S3 Access

1. Go to **IAM → Users → Create user**
   - Username: `cateringco-s3`
2. **Attach policies directly** → select **AmazonS3FullAccess** (or create a scoped policy)
3. After creation → **Security credentials → Create access key**
   - Use case: Application running outside AWS
   - Save the **Access key ID** and **Secret access key** — shown once only

### 2.3 Update S3 Environment Variables

In `.env.production` on EC2:
```
R2_ACCESS_KEY=YOUR_IAM_ACCESS_KEY_ID
R2_SECRET_KEY=YOUR_IAM_SECRET_ACCESS_KEY
R2_ENDPOINT=https://s3.us-east-1.amazonaws.com   # change region if needed
R2_BUCKET=catering-uploads-avinash
```

> The app uses S3-compatible env vars (`R2_*`) — AWS S3 is fully compatible with this.

---

## Part 3 — EC2 (Backend Services)

### 3.1 Launch EC2 Instance

1. Go to **EC2 → Launch Instance**
2. Settings:
   - Name: `cateringco-backend`
   - AMI: **Ubuntu Server 22.04 LTS**
   - Instance type: `t3.small` (2 vCPU, 2 GB) — minimum; `t3.medium` recommended
   - Key pair: create or use existing — **download the `.pem` file**
   - Network settings:
     - VPC: same VPC as your RDS
     - Auto-assign public IP: **Enable**
     - Create security group: `ec2-cateringco`
       - Inbound: SSH (22), Custom TCP 3001, Custom TCP 8000
3. Storage: 20 GB gp3
4. Click **Launch Instance**

### 3.2 Allow RDS to Accept EC2 Connections

Go back to your RDS security group (`rds-cateringco`) → Edit inbound rules:
- Type: PostgreSQL (5432)
- Source: **security group** `ec2-cateringco`

### 3.3 SSH into EC2

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@EC2_PUBLIC_IP
```

### 3.4 Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker compose version   # should show v2.x
```

### 3.5 Clone the Repo

```bash
git clone <your-repo-url> app
cd app
git checkout deploy
```

### 3.6 Create the Production Env File

```bash
cp .env.production.example .env.production
nano .env.production
```

Fill in:

```bash
# Database — RDS connection string
DATABASE_URL=postgresql://cateringco:YOUR_PASSWORD@YOUR_RDS_ENDPOINT:5432/cateringco_prod

# Auth — generate both:
# openssl rand -base64 48
JWT_SECRET=...
JWT_REFRESH_SECRET=...

# AI
OPENAI_API_KEY=sk-...

# Storage — S3
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_ENDPOINT=https://s3.us-east-1.amazonaws.com
R2_BUCKET=catering-uploads-avinash

# CORS — your Vercel URL (fill after Part 4)
CORS_ORIGIN=https://FILL_IN.vercel.app
```

### 3.7 Create the Database on RDS

Before starting the app, create the database on RDS:

```bash
# Install psql client
sudo apt install postgresql-client -y

# Create the database
psql postgresql://cateringco:YOUR_PASSWORD@YOUR_RDS_ENDPOINT:5432/postgres \
  -c "CREATE DATABASE cateringco_prod;"
```

### 3.8 Start All Backend Services

```bash
docker compose -f docker-compose.gcp.yml --env-file .env.production up -d --build
```

> `docker-compose.gcp.yml` starts: **redis, backend, workers, ml-agent**
> Postgres is NOT started (it's on RDS). The backend connects to RDS via `DATABASE_URL`.
> Migrations run automatically on backend startup.

### 3.9 Verify

```bash
docker compose -f docker-compose.gcp.yml ps
# Should show redis, backend, workers, ml-agent as Up/healthy

docker compose -f docker-compose.gcp.yml logs backend --tail=30
docker compose -f docker-compose.gcp.yml logs ml-agent --tail=30
```

Test from your browser:
```
http://EC2_PUBLIC_IP:3001/api      → backend health
http://EC2_PUBLIC_IP:8000/health   → ml-agent health
```

---

## Part 4 — Vercel (Frontend)

### 4.1 Push the deploy branch

```bash
git push origin deploy
```

### 4.2 Import on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repo
3. Set **Root Directory** to `frontend`
4. Framework auto-detects as Next.js

### 4.3 Set Environment Variables in Vercel

In Vercel → Project Settings → **Environment Variables**:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `http://EC2_PUBLIC_IP:3001` |
| `NEXT_PUBLIC_ML_API_URL` | `http://EC2_PUBLIC_IP:8000` |
| `NEXT_PUBLIC_WS_URL` | `ws://EC2_PUBLIC_IP:3001` |

> Once you add a domain + SSL, change these to `https://` and `wss://`.

### 4.4 Deploy

Click **Deploy**. Copy your Vercel URL after deploy (e.g. `https://the-catering-company.vercel.app`).

### 4.5 Update CORS on EC2

```bash
# On EC2:
nano .env.production
# Set: CORS_ORIGIN=https://the-catering-company.vercel.app

docker compose -f docker-compose.gcp.yml --env-file .env.production up -d backend
```

---

## Database (RDS)

Migrations run automatically on every backend startup via `prisma migrate deploy`.

**Manual connection:**
```bash
psql postgresql://cateringco:PASSWORD@YOUR_RDS_ENDPOINT:5432/cateringco_prod
```

**Backup:**
```bash
pg_dump postgresql://cateringco:PASSWORD@YOUR_RDS_ENDPOINT:5432/cateringco_prod \
  > backup_$(date +%Y%m%d).sql
```

**Restore:**
```bash
psql postgresql://cateringco:PASSWORD@YOUR_RDS_ENDPOINT:5432/cateringco_prod \
  < backup_YYYYMMDD.sql
```

RDS handles automated backups, multi-AZ failover, and point-in-time recovery automatically.

---

## Deploying Updates

```bash
# On EC2:
cd app
git pull origin deploy
docker compose -f docker-compose.gcp.yml --env-file .env.production up -d --build
```

Vercel auto-deploys on every push to `deploy` branch.

---

## Optional: Custom Domain + HTTPS

1. **Elastic IP** — assign a static IP to your EC2 (EC2 → Elastic IPs → Allocate)
2. Point your domain DNS to the Elastic IP (A record for `api.yourdomain.com` and `ml.yourdomain.com`)
3. Install Nginx + Certbot on EC2:
   ```bash
   sudo apt install nginx certbot python3-certbot-nginx -y
   ```
4. Create Nginx config to reverse proxy ports 3001 and 8000
5. Run `sudo certbot --nginx` for free SSL
6. Update Vercel env vars to `https://api.yourdomain.com` etc.
7. Update `CORS_ORIGIN` to your frontend domain and restart backend

---

## Quick Reference

| What | Command (on EC2) |
|------|---------|
| Start all | `docker compose -f docker-compose.gcp.yml --env-file .env.production up -d --build` |
| Stop all | `docker compose -f docker-compose.gcp.yml down` |
| View logs | `docker compose -f docker-compose.gcp.yml logs -f SERVICE` |
| Restart service | `docker compose -f docker-compose.gcp.yml restart backend` |
| Service status | `docker compose -f docker-compose.gcp.yml ps` |
| DB backup | see Database section above |
