import { defineConfig } from '@playwright/test';
import process from 'node:process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const envFile = fileURLToPath(new URL('../tools/qa/scrum149/.env.local', import.meta.url));
if (existsSync(envFile)) process.loadEnvFile(envFile);

export default defineConfig({
  testDir: './e2e-qa',
  testMatch: ['catalogo-real.spec.js', 'accesibilidad-real.spec.js'],
  workers: 1,
  timeout: 60_000,
  reporter: [['list'], ['json', { outputFile: process.env.QA149_RESULTS || '../.tmp/scrum149/browser.json' }]],
  outputDir: process.env.QA149_ARTIFACTS || '../.tmp/scrum149/browser-artifacts',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
    channel: 'msedge',
    // La prueba administrativa usa credenciales: no registrar tokens en trazas.
    trace: 'off',
    screenshot: 'only-on-failure',
  },
  webServer: {
    // Para QA, compilar con VITE_API_URL=http://127.0.0.1:8000/api/ (guía SCRUM-148).
    // Django escucha en IPv4; localhost puede resolverse a IPv6 en Edge/Windows.
    command: 'npm run preview -- --host 127.0.0.1 --port 5173 --strictPort',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: false,
  },
});
