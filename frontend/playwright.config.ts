// Playwright tests against the LIVE site (read-only checks). One project per tester:
//   V = Vineet, S = Nishita, K = Kunal. Each person runs their own: npx playwright test --project=V
// Logins come from frontend/.env.e2e.local (git-ignored, see e2e/README.md). Nothing secret is in this file.
import { existsSync } from 'node:fs';
import { defineConfig, devices } from '@playwright/test';

if (existsSync('.env.e2e.local')) process.loadEnvFile('.env.e2e.local');

export const TESTERS = ['V', 'S', 'K'] as const;

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  // Live site on Render's free plan: the first call may wait ~50 s while the server wakes up
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: 0, // a flaky page should show up in the report, not be hidden by a retry
  workers: 2,
  reporter: [['list'], ['html', { open: 'never' }], ['json', { outputFile: 'test-results/results.json' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'https://kjs-m.vercel.app',
    ...devices['Desktop Chrome'],
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    ...TESTERS.flatMap((t) => [
      // Logs in once and saves the session to .auth/<t>.json (git-ignored)
      { name: `setup-${t}`, testMatch: /auth\.setup\.ts/, metadata: { tester: t } },
      {
        name: t,
        testMatch: /portal\.spec\.ts/,
        dependencies: [`setup-${t}`],
        metadata: { tester: t },
        use: { storageState: `.auth/${t}.json` },
      },
    ]),
    // A = the admin test account: the admin module, end to end (docs/testing/admin-e2e.xlsx).
    // Run it on its own: npx playwright test --project=A
    { name: 'setup-A', testMatch: /auth\.setup\.ts/, metadata: { tester: 'A' } },
    {
      name: 'A',
      testMatch: /admin\.spec\.ts/,
      dependencies: ['setup-A'],
      metadata: { tester: 'A' },
      use: { storageState: '.auth/A.json' },
    },
  ],
});
