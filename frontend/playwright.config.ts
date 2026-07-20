import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:4173",
    channel: "chrome",
    headless: true,
  },
  webServer: [
    {
      command: "../.venv/bin/python ../scripts/e2e_server.py",
      url: "http://127.0.0.1:8787/health",
      reuseExistingServer: false,
      timeout: 20_000,
    },
    {
      command: "npm run dev -- --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
      timeout: 20_000,
    },
  ],
});
