#!/usr/bin/env node
/**
 * Usage:
 *   npm run env:dev   → frontend → localhost, backend → local Postgres
 *   npm run env:prod  → frontend → prod server, backend → RDS via SSH tunnel
 *
 * For prod DB locally:
 *   npm run db:tunnel   → opens SSH tunnel  localhost:5433 → EC2 → RDS
 *   npm run env:dev     → already points backend to localhost:5433 when tunnel is active
 *
 * Or just run:
 *   npm run dev:rds     → tunnel + env:rds in one step
 */

const fs   = require('fs');
const path = require('path');

const FRONTEND_ENV = path.resolve(__dirname, '../.env.local');
const BACKEND_ENV  = path.resolve(__dirname, '../../backend/.env');
const ML_AGENT_ENV = path.resolve(__dirname, '../../../TheCateringCompanyAgent/.env');

// ── Constants ─────────────────────────────────────────────────────────────────
const EC2_HOST   = '13.219.232.214';
const EC2_USER   = 'ubuntu';
const PEM_KEY    = 'C:/Users/avina/catering-ec2-key.pem';
const RDS_HOST   = 'cateringstack-databaseb269d8bb-fyvvsozwqbxz.c4xcoo4kyogb.us-east-1.rds.amazonaws.com';
const RDS_PORT   = 5432;
const TUNNEL_PORT = 5433;          // local port that forwards to RDS through EC2

// RDS creds — used via tunnel (localhost:5433) or directly on EC2 (prod)
const RDS_URL_DIRECT = `postgresql://cateringco:CateringProd2026%21@${RDS_HOST}:${RDS_PORT}/cateringco_prod?sslmode=require`;
const RDS_URL_TUNNEL = `postgresql://cateringco:CateringProd2026%21@localhost:${TUNNEL_PORT}/cateringco_prod?sslmode=require`;
const LOCAL_DB_URL   = 'postgresql://avinash:Avinash%401617@localhost:5432/caterDB_prod';

const JWT_SECRET         = 'Z0r4p8h1nQxV9mW2LkT6uCj3yB5fG7sR+eA1dH8PqXc=';
const JWT_REFRESH_SECRET = 'Y6tFvJ3mQ9Kp2Xr8hLzB1cN5eW7uD4sG+aE0MZqRjTw=';
const DOCUSEAL_API_KEY   = 'mgN1UEE27SFNpBbsWLPdu96N6NfyEyqggevEm82TzSG';

const SHARED_BACKEND = {
  REDIS_URL:           'redis://localhost:6379',
  JWT_SECRET,
  JWT_REFRESH_SECRET,
  BACKEND_PORT:        '3001',
  DOCUSEAL_ENABLED:    'true',
  DOCUSEAL_API_KEY,
  DOCUSEAL_API_URL:    'https://api.docuseal.co',
  DOCUSEAL_SIGNING_URL:'https://docuseal.co',
  RATE_LIMIT_TTL:      '60',
  RATE_LIMIT_MAX:      '100',
};

// ── Configs ───────────────────────────────────────────────────────────────────
const configs = {
  // Local frontend + local Postgres
  dev: {
    frontend: {
      NEXT_PUBLIC_API_URL:    'http://localhost:3001',
      NEXT_PUBLIC_WS_URL:     'ws://localhost:3001',
      NEXT_PUBLIC_ML_API_URL: 'http://localhost:8000',
    },
    backend: {
      DATABASE_URL: LOCAL_DB_URL,
      NODE_ENV:     'development',
      CORS_ORIGIN:  'http://localhost:3000',
      ...SHARED_BACKEND,
    },
  },

  // Local frontend + RDS via SSH tunnel (run `npm run db:tunnel` first)
  rds: {
    frontend: {
      NEXT_PUBLIC_API_URL:    'http://localhost:3001',
      NEXT_PUBLIC_WS_URL:     'ws://localhost:3001',
      NEXT_PUBLIC_ML_API_URL: 'http://localhost:8000',
    },
    backend: {
      DATABASE_URL:                 RDS_URL_TUNNEL,
      NODE_ENV:                     'development',
      CORS_ORIGIN:                  'http://localhost:3000',
      NODE_TLS_REJECT_UNAUTHORIZED: '0',
      ...SHARED_BACKEND,
    },
    mlAgent: {
      DATABASE_URL: `"${RDS_URL_TUNNEL}"`,
    },
  },

  // Prod server + RDS directly (runs on EC2)
  prod: {
    frontend: {
      NEXT_PUBLIC_API_URL:    `http://${EC2_HOST}:3001`,
      NEXT_PUBLIC_WS_URL:     `ws://${EC2_HOST}:3001`,
      NEXT_PUBLIC_ML_API_URL: `http://${EC2_HOST}:8000`,
    },
    backend: {
      DATABASE_URL:                 RDS_URL_DIRECT,
      NODE_ENV:                     'production',
      CORS_ORIGIN:                  `http://${EC2_HOST}:3000`,
      NODE_TLS_REJECT_UNAUTHORIZED: '0',
      ...SHARED_BACKEND,
    },
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function writeEnv(filePath, vars) {
  const content = Object.entries(vars).map(([k, v]) => `${k}=${v}`).join('\n') + '\n';
  fs.writeFileSync(filePath, content, 'utf8');
}

const SENSITIVE = ['DATABASE_URL', 'JWT_SECRET', 'JWT_REFRESH_SECRET', 'DOCUSEAL_API_KEY'];

function printSection(label, vars) {
  console.log(`\n  [${label}]`);
  Object.entries(vars).forEach(([k, v]) => {
    console.log(`    ${k}=${SENSITIVE.includes(k) ? '****' : v}`);
  });
}

// ── Tunnel command ────────────────────────────────────────────────────────────
function printTunnelCmd() {
  console.log('\n┌─ SSH Tunnel command ─────────────────────────────────────────┐');
  console.log(`│  ssh -i "${PEM_KEY}"`);
  console.log(`│      -L ${TUNNEL_PORT}:${RDS_HOST}:${RDS_PORT}`);
  console.log(`│      ${EC2_USER}@${EC2_HOST} -N`);
  console.log('│');
  console.log(`│  Forwards  localhost:${TUNNEL_PORT}  →  EC2  →  RDS`);
  console.log('│  Keep this terminal open while using the RDS DB locally.');
  console.log('└──────────────────────────────────────────────────────────────┘\n');
}

// ── Main ──────────────────────────────────────────────────────────────────────
const mode = process.argv[2];

if (!configs[mode]) {
  console.error('\n  Usage: node set-env.js <dev|rds|prod>\n');
  console.error('    dev  — local Postgres');
  console.error('    rds  — RDS via SSH tunnel (localhost:5433 → EC2 → RDS)');
  console.error('    prod — production server config\n');
  process.exit(1);
}

const { frontend, backend, mlAgent } = configs[mode];

writeEnv(FRONTEND_ENV, frontend);
writeEnv(BACKEND_ENV, backend);
if (mlAgent) {
  // Preserve existing ML agent .env keys (like OPENAI_API_KEY) and only update DATABASE_URL
  let mlContent = '';
  try { mlContent = fs.readFileSync(ML_AGENT_ENV, 'utf8'); } catch {}
  const mlLines = mlContent.split('\n').filter(l => l && !l.startsWith('DATABASE_URL'));
  mlLines.unshift(`DATABASE_URL=${mlAgent.DATABASE_URL}`);
  fs.writeFileSync(ML_AGENT_ENV, mlLines.join('\n') + '\n', 'utf8');
}

console.log(`\n✓ Environment set to [${mode.toUpperCase()}]`);
printSection('frontend/.env.local', frontend);
printSection('backend/.env', backend);
if (mlAgent) printSection('TheCateringCompanyAgent/.env', mlAgent);

if (mode === 'rds') {
  console.log('\n  ⚠  Make sure the SSH tunnel is open before starting the backend.');
  printTunnelCmd();
} else {
  console.log('\n  Restart backend + frontend dev servers for changes to take effect.\n');
}
