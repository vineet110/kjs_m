// Playwright: read-only smoke tests on the live site (e2e/TEST-CASES.md).
// One project per tester (V, S, K). Each person runs only their own: `npx playwright test --project=K`.
// The login comes from frontend/.env.e2e.local (git-ignored): E2E_EMAIL and E2E_PASSWORD.
import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { STORAGE } from './e2e/helpers';

const envFile = path.resolve(__dirname, '.env.e2e.local');
if (existsSync(envFile)) process.loadEnvFile(envFile); // built into Node 20.12+, no extra package

// Whose account each project expects (TC05 checks it, so nobody runs a project with the wrong login)
const TESTERS = { V: 'v@testerv.com', S: 's@testers.com', K: 'k@testsk.com' };

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000, // the free API server can be slow to wake up
  expect: { timeout: 20_000 },
  fullyParallel: true,
  workers: 2, // gentle on the live site: three people run at the same time
  retries: 0, // no retry loops: a retry could mean another login
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'https://kjs-m.vercel.app',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    ...Object.entries(TESTERS).map(([name, email]) => ({
      name,
      testMatch: /.*\.spec\.ts/,
      dependencies: ['setup'],
      metadata: { email },
      use: { ...devices['Desktop Chrome'], storageState: STORAGE },
    })),
  ],
});
