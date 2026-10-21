const { test, expect } = require('@playwright/test');
const { controlledSite } = require('./site-helpers');

test.beforeEach(async ({ page }) => { await controlledSite(page); });

test('find a title, read details, and locate its shelf', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('#bookCount')).toHaveText('2');
  await expect(page.locator('.map-legend')).toContainText('Number = cataloged books');
  await expect(page.locator('.leaflet-marker-icon[title*="CSN-0001"]')).toHaveAttribute('title', 'CSN-0001 · Maple Street Library · 2 books');
  await page.locator('#searchQuery').fill('secret garden');
  await page.locator('#searchForm').getByRole('button', { name: 'Find books', exact: true }).click();
  const card = page.locator('.result-card');
  await expect(card).toHaveCount(1);
  await expect(card.getByRole('heading')).toHaveText('The Secret Garden');
  await expect(card).toContainText('Frances Hodgson Burnett');
  await card.getByText('Book details', { exact: true }).click();
  await expect(card).toContainText('Example Press');
  await card.getByRole('button', { name: 'Show on map' }).click();
  await expect(page.locator('.leaflet-popup')).toContainText('Maple Street Library');
  expect(errors).toEqual([]);
});

test('search is in the first viewport and layouts tolerate larger text', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(page.locator('#searchQuery')).toBeEnabled();
  const box = await page.locator('#searchQuery').boundingBox();
  expect(box.y + box.height).toBeLessThan(page.viewportSize().height);
  const noOverflow = () => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);
  expect(await noOverflow()).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('initial.png'), fullPage: true });
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  expect(await noOverflow()).toBe(true);
  await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Contribute' })).toBeVisible();
});

test('keyboard skip link reaches search and contribution link reaches guidance', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to search' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#searchTitle')).toBeFocused();
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Contribute' }).click();
  await expect(page).toHaveURL(/#contribute$/);
  await expect(page.getByRole('link', { name: 'Send photos by email' })).toBeVisible();
});

test('denied location gives a ZIP recovery path', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'geolocation', { value: {
      getCurrentPosition: (_success, failure) => failure({ code: 1, message: 'Denied' }),
    } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Use my location' }).click();
  await expect(page.locator('#locationStatus')).toContainText('ZIP');
  await page.locator('#zipCode').fill('20877');
  await page.locator('#searchQuery').fill('garden');
  await page.getByRole('button', { name: 'Find books', exact: true }).click();
  await expect(page.locator('.result-card')).toContainText('0.0 mi');
});

test('failed ZIP lookup offers an explicit search without location', async ({ page }) => {
  await page.route('https://api.zippopotam.us/**', route => route.fulfill({ status: 503, body: '' }));
  await page.goto('/');
  await page.locator('#zipCode').fill('99999');
  await page.locator('#searchQuery').fill('garden');
  await page.getByRole('button', { name: 'Find books', exact: true }).click();
  await page.getByRole('button', { name: 'Search all locations' }).click();
  await expect(page.locator('.result-card')).toContainText('The Secret Garden');
  await expect(page.locator('#zipCode')).toHaveValue('');
});

test('data failures can be retried and controls wait for data', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/atlas-data.json', async route => {
    await gate;
    await route.fulfill({ status: 503, body: '' });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#searchQuery')).toBeDisabled();
  release();
  await expect(page.getByRole('button', { name: 'Retry loading' })).toBeVisible();
  await page.unroute('**/atlas-data.json');
  const { fixture } = require('./site-helpers');
  await page.route('**/atlas-data.json', route => route.fulfill({ json: fixture }));
  await page.getByRole('button', { name: 'Retry loading' }).click();
  await expect(page.locator('#searchQuery')).toBeEnabled();
  await expect(page.locator('#bookCount')).toHaveText('2');
});

test('search remains useful when the map library is unavailable', async ({ page }) => {
  await page.route('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', route => route.abort());
  await page.goto('/');
  await page.locator('#searchQuery').fill('garden');
  await page.getByRole('button', { name: 'Find books', exact: true }).click();
  await expect(page.locator('.result-card')).toContainText('Maple Street Library');
  await expect(page.locator('.result-card').getByRole('link', { name: 'Directions' })).toHaveAttribute('href', /maps/);
  await expect(page.locator('.result-card').getByRole('button', { name: 'Show on map' })).toHaveCount(0);
});

test('no matching books gives a way to clear the query', async ({ page }) => {
  await page.goto('/');
  await page.locator('#searchQuery').fill('unmatched-example');
  await page.getByRole('button', { name: 'Find books', exact: true }).click();
  await expect(page.locator('#results')).toContainText('No books matched');
  await page.getByRole('button', { name: 'Clear search' }).click();
  await expect(page.locator('#searchQuery')).toHaveValue('');
  await expect(page.locator('#results')).toContainText('Not sure what to read');
});
