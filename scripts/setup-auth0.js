#!/usr/bin/env node
/**
 * Interactive Auth0 setup - adds Domain and Client ID to .env
 * Run: node scripts/setup-auth0.js
 */
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const envPath = path.join(__dirname, '..', '.env');

function main() {
  const env = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : '';
  const hasPlaceholder = /AUTH0_CLIENT_ID=your_client_id/.test(env) || /AUTH0_DOMAIN=your-tenant\.us\.auth0\.com/.test(env);

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const ask = (q) => new Promise(res => rl.question(q, res));

  (async () => {
    console.log('Auth0 Setup\n');
    console.log('Get these from: Auth0 Dashboard → Applications → Your App → Settings\n');

    const domain = await ask('AUTH0_DOMAIN (e.g. dev-xxxxx.us.auth0.com): ');
    const clientId = await ask('AUTH0_CLIENT_ID: ');
    rl.close();

    if (!domain.trim() || !clientId.trim()) {
      console.log('Skipped - both values required.');
      process.exit(1);
    }

    let updated = env
      .replace(/AUTH0_DOMAIN=.*/g, `AUTH0_DOMAIN=${domain.trim()}`)
      .replace(/AUTH0_CLIENT_ID=.*/g, `AUTH0_CLIENT_ID=${clientId.trim()}`);

    if (!updated.includes('AUTH0_DOMAIN=')) {
      updated += `\nAUTH0_DOMAIN=${domain.trim()}`;
    }
    if (!updated.includes('AUTH0_CLIENT_ID=')) {
      updated += `\nAUTH0_CLIENT_ID=${clientId.trim()}`;
    }

    fs.writeFileSync(envPath, updated);
    console.log('\n✓ .env updated. Restart the server: npm start');
  })();
}

main();
