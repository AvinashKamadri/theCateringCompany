#!/usr/bin/env node
/**
 * Mini script to test Gmail OAuth flow.
 * Usage: node scripts/test-gmail-oauth.js <email> <password>
 * Example: node scripts/test-gmail-oauth.js admin@company.com mypassword
 */

const [,, email, password] = process.argv;

if (!email || !password) {
  console.error('Usage: node scripts/test-gmail-oauth.js <email> <password>');
  process.exit(1);
}

const BASE = 'http://localhost:3001/api';

async function run() {
  // Step 1 — Login to get JWT
  console.log(`\n[1] Logging in as ${email}...`);
  const loginRes = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!loginRes.ok) {
    const err = await loginRes.text();
    console.error('Login failed:', err);
    process.exit(1);
  }

  const loginData = await loginRes.json();
  const token = loginData.accessToken ?? loginData.access_token ?? loginData.token;

  if (!token) {
    console.error('No token in response:', JSON.stringify(loginData));
    process.exit(1);
  }
  console.log('    JWT obtained');

  // Step 2 — Get Gmail OAuth URL
  console.log('\n[2] Fetching Gmail OAuth URL...');
  const authRes = await fetch(`${BASE}/gmail/auth`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!authRes.ok) {
    const err = await authRes.text();
    console.error('Failed to get auth URL:', err);
    process.exit(1);
  }

  const { url } = await authRes.json();
  console.log('\n[3] Open this URL in your browser to connect Gmail:\n');
  console.log('  ', url);
  console.log('\n    After consent, Google redirects to /gmail/callback');
  console.log('    which stores the encrypted token and enqueues gmail-full-sync.\n');

  // Step 3 — Try to auto-open in browser (best effort)
  const { exec } = require('child_process');
  const open =
    process.platform === 'win32' ? `start "" "${url}"` :
    process.platform === 'darwin' ? `open "${url}"` :
    `xdg-open "${url}"`;

  exec(open, (err) => {
    if (err) console.log('    (Could not auto-open browser — copy the URL above manually)');
    else console.log('    Browser opened automatically.');
  });

  // Step 4 — Check Gmail connection status after redirect
  console.log('\n[4] Checking connection status (run this after completing consent):\n');
  console.log(`    curl ${BASE}/gmail/status -H "Authorization: Bearer ${token}"\n`);
}

run().catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
