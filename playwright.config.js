const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/browser',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    reducedMotion: 'reduce',
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'phone-390', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
    { name: 'phone-360', use: { viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: 'python -m http.server 8765 --bind 127.0.0.1 --directory docs',
    url: 'http://127.0.0.1:8765',
    reuseExistingServer: !process.env.CI,
  },
});
