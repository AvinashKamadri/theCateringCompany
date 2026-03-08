# Production Deployment Checklist

## Pre-Deployment Security Review

### ✅ Environment Variables
- [ ] All `.env` files are in `.gitignore` (✓ Done)
- [ ] Created `.env.example` template without secrets (✓ Done)
- [ ] Changed `JWT_SECRET` to strong random value (min 32 chars)
- [ ] Changed `JWT_REFRESH_SECRET` to different strong value
- [ ] Set `NODE_ENV=production`
- [ ] Verified no hardcoded secrets in codebase

### ✅ Database
- [ ] Applied production schema: `npx prisma migrate deploy`
- [ ] Created database backups
- [ ] Set connection pool limits appropriately
- [ ] Enabled SSL for database connections
- [ ] Updated `DATABASE_URL` with production credentials

### ✅ Authentication & Security
- [ ] HTTP-only cookies enabled (✓ Already configured)
- [ ] CORS configured for production domain (update `CORS_ORIGIN`)
- [ ] Rate limiting configured
- [ ] Helmet.js enabled for security headers
- [ ] HTTPS enforced (redirect HTTP → HTTPS)

### ✅ Stripe Integration
- [ ] Set `STRIPE_ENABLED=true`
- [ ] Use live keys (`sk_live_...` not `sk_test_...`)
- [ ] Configure webhook endpoint in Stripe Dashboard
- [ ] Set `STRIPE_WEBHOOK_SECRET` from Stripe
- [ ] Test payment flow end-to-end

### ✅ File Storage (R2/S3)
- [ ] Create production bucket
- [ ] Set CORS policy on bucket
- [ ] Configure R2 credentials (`R2_ACCESS_KEY`, `R2_SECRET_KEY`)
- [ ] Test file upload/download

### ✅ Redis & Background Jobs
- [ ] Redis instance running (managed service recommended)
- [ ] Update `REDIS_URL` with production endpoint
- [ ] Workers deployed and running
- [ ] Monitor job queue health

### ✅ Notifications
- [ ] Set `NOTIFICATION_MOCK=false`
- [ ] Configure SendGrid API key
- [ ] Verify sender email domain
- [ ] Set up Twilio for SMS (optional)

### ✅ Monitoring & Logging
- [ ] Set up Sentry for error tracking (`SENTRY_DSN`)
- [ ] Configure log aggregation (e.g., CloudWatch, Datadog)
- [ ] Set up uptime monitoring
- [ ] Create alerts for critical errors

### ✅ Infrastructure
- [ ] Database has automated backups
- [ ] Redis has persistence enabled
- [ ] Load balancer configured (if multi-instance)
- [ ] CDN configured for static assets
- [ ] SSL certificates valid and auto-renewing

### ✅ Code Quality
- [ ] All tests passing: `npm run test`
- [ ] No TypeScript errors: `npm run build`
- [ ] Linter passing: `npm run lint`
- [ ] Dependencies updated and audited: `npm audit`

### ✅ Git & Version Control
- [ ] `.gitignore` configured (✓ Done)
- [ ] No sensitive files in git history
- [ ] Tagged release version: `git tag v1.0.0`
- [ ] Pushed to production branch

---

## Environment Variable Checklist

Copy from `.env.example` and fill these for production:

### Critical (Must Change)
```bash
JWT_SECRET=                    # Generate: openssl rand -base64 32
JWT_REFRESH_SECRET=            # Generate: openssl rand -base64 32
DATABASE_URL=                  # Production PostgreSQL URL
REDIS_URL=                     # Production Redis URL
CORS_ORIGIN=                   # Your production domain
```

### Payments (If enabled)
```bash
STRIPE_ENABLED=true
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Storage (If using R2/S3)
```bash
R2_ACCESS_KEY=
R2_SECRET_KEY=
R2_ENDPOINT=
R2_BUCKET=
```

### Notifications (If enabled)
```bash
NOTIFICATION_MOCK=false
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=
```

---

## Deployment Commands

### 1. Build Backend
```bash
cd backend
npm install --production
npx prisma generate
npx prisma migrate deploy
npm run build
```

### 2. Build Frontend
```bash
cd frontend
npm install --production
npm run build
```

### 3. Build Workers
```bash
cd workers
npm install --production
npm run build
```

### 4. Start Services
```bash
# Backend
cd backend && npm run start:prod

# Workers (separate process)
cd workers && npm run start

# Frontend (if self-hosting, or deploy to Vercel)
cd frontend && npm start
```

---

## Post-Deployment Verification

### Health Checks
- [ ] `GET /api/auth/me` returns 401 (unauthenticated)
- [ ] `POST /api/auth/signup` creates user successfully
- [ ] `POST /api/auth/login` returns JWT cookie
- [ ] WebSocket connects at `wss://your-domain.com`
- [ ] Background jobs processing (check Redis queues)

### Integration Tests
- [ ] Create project → Success
- [ ] Create contract → Success
- [ ] Generate PDF → Job queued and processed
- [ ] Create payment intent → Stripe PI created
- [ ] Send message → Real-time event received
- [ ] Upload attachment → File in R2/S3

### Performance
- [ ] Response time < 200ms for API endpoints
- [ ] WebSocket latency < 100ms
- [ ] Database connection pool not exhausted
- [ ] Redis memory usage stable

---

## Rollback Plan

If deployment fails:

1. **Revert code**: `git revert <commit-hash>`
2. **Rollback database**: `npx prisma migrate resolve --rolled-back <migration>`
3. **Check logs**: Review error logs for root cause
4. **Restore from backup**: If data corrupted

---

## Security Hardening

### Before Going Live
```bash
# Audit dependencies
npm audit fix

# Check for secrets in git
git log -p | grep -i "password\|secret\|key"

# Scan for vulnerabilities
npx snyk test

# Check Docker images (if using)
docker scan your-image:latest
```

### Recommended Security Headers
Already configured via Helmet.js, but verify:
- `Strict-Transport-Security`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `Content-Security-Policy`

---

## Support & Monitoring

### Key Metrics to Track
- API response times (p50, p95, p99)
- Error rate (4xx, 5xx)
- Database query performance
- Redis queue length
- WebSocket connection count
- Background job success/failure rate

### Log What Matters
- Authentication attempts (success/failure)
- Payment transactions
- Webhook deliveries
- File uploads
- Background job processing
- API errors with stack traces

---

## Quick Reference

| Service | Production Port | Health Check |
|---------|----------------|--------------|
| Backend | 443 (HTTPS) | `GET /health` |
| Frontend | 443 (HTTPS) | `GET /` |
| WebSocket | 443 (WSS) | Connect test |
| Database | 5432 | `SELECT 1` |
| Redis | 6379 | `PING` |

---

## Need Help?

- Backend API: See [API_DOCUMENTATION.md](backend/API_DOCUMENTATION.md)
- Database Schema: See [sql/schema_final.sql](sql/schema_final.sql)
- Environment Setup: See [backend/.env.example](backend/.env.example)
