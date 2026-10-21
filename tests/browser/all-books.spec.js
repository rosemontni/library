const { test, expect } = require('@playwright/test');
const { controlledSite, fixture } = require('./site-helpers');

test('All Books is a separate page sorted by Dewey, LCC, then unclassified with pagination', async ({ page }) => {
  const books = [
    { id: 100, library_id: 1, title: 'Dewey later', ddc_numbers: ['635.1'] },
    { id: 101, library_id: 1, title: 'Dewey earlier', ddc_numbers: ['635.09'] },
    { id: 102, library_id: 1, title: 'Dewey first', ddc_numbers: ['100'] },
    { id: 103, library_id: 1, title: 'LCC later', lcc_numbers: ['QA76.A2'] },
    { id: 104, library_id: 1, title: 'LCC earlier', lcc_numbers: ['QA76.A19'] },
    ...Array.from({ length: 25 }, (_, id) => ({ id: id + 200, library_id: 1, title: `Unclassified ${id + 1}` })),
  ];
  await controlledSite(page, { data: { ...fixture, books, counts: { libraries: 2, books: 30 } } });
  await page.goto('/');
  await expect(page.locator('#allBooksResults')).toHaveCount(0);
  await page.getByRole('navigation').getByRole('link', { name: 'All Books', exact: true }).click();
  await expect(page).toHaveURL(/books\.html$/);
  const titles = page.locator('#allBooksResults .result-card h3');
  await expect(titles).toHaveCount(24);
  expect((await titles.allTextContents()).slice(0, 5)).toEqual(['Dewey first', 'Dewey earlier', 'Dewey later', 'LCC earlier', 'LCC later']);
  await expect(page.locator('#pageNumber')).toHaveText('Page 1 of 2');
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(titles).toHaveCount(6);
  await page.getByRole('button', { name: 'Previous', exact: true }).click();
  await expect(titles).toHaveCount(24);
  await page.locator('#allBooksResults .result-card').first().getByRole('link', { name: 'Show on map' }).click();
  await expect(page.locator('.leaflet-popup')).toContainText('Maple Street Library');
});

test('catalog supports empty data and legacy All Books links', async ({ page }) => {
  await controlledSite(page, { data: { ...fixture, books: [], counts: { libraries: 2, books: 0 } } });
  await page.goto('/#allBooks');
  await expect(page).toHaveURL(/books\.html$/);
  await expect(page.locator('#allBooksResults')).toHaveText('No books are cataloged yet.');
  await expect(page.locator('#nextPage')).toBeDisabled();
});

test('catalog filters, source details, retry, and browser history work', async ({ page }) => {
  await controlledSite(page, { data: { ...fixture, books: [{ ...fixture.books[0], ddc_numbers: ['635.9'], lcc_numbers: ['SB450.S65'], classification_sources: ['https://openlibrary.org/works/OL123W'] }, fixture.books[1]] } });
  let failed = true;
  await page.route('**/atlas-data.json', route => failed ? route.fulfill({ status: 503, body: 'Unavailable' }) : route.fallback());
  await page.goto('/books.html');
  await expect(page.locator('#retryAllBooks')).toBeVisible();
  failed = false;
  await page.locator('#retryAllBooks').click();
  await expect(page.locator('#catalogQuery')).toBeEnabled();
  await page.locator('#catalogQuery').fill('SB450.S65');
  await page.getByRole('button', { name: 'Filter books' }).click();
  await expect(page.locator('.result-card')).toHaveCount(1);
  await page.getByText('Book details', { exact: true }).click();
  await expect(page.locator('.result-card')).toContainText('edition unverified');
  await expect(page.getByRole('link', { name: 'Classification source' })).toHaveAttribute('href', 'https://openlibrary.org/works/OL123W');
  await page.locator('#catalogQuery').fill('');
  await page.locator('#catalogSystem').selectOption('review');
  await page.getByRole('button', { name: 'Filter books' }).click();
  await expect(page.locator('.result-card h3')).toHaveText('A Field Guide to Birds');
  await page.goBack();
  await expect(page.locator('#catalogQuery')).toHaveValue('SB450.S65');
  await expect(page.locator('.result-card h3')).toHaveText('The Secret Garden');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});

test('home shows newest and oldest publication highlights and category frequency', async ({ page }) => {
  const books = [
    { id: 1, library_id: 1, title: 'Recent Book', genre: 'Nature', published_year: '2024' },
    { id: 2, library_id: 1, title: 'Historic Book', genre: 'Nature', published_year: '1800' },
    { id: 3, library_id: 1, title: 'Recent Book', genre: 'Nature', published_year: '2024' },
    { id: 4, library_id: 1, title: 'No category', genre: '' },
  ];
  await controlledSite(page, { data: { ...fixture, books } });
  await page.goto('/');
  const highlights = page.locator('#databaseSummary');
  await expect(highlights.getByRole('heading', { name: 'Newest books · Hot off the Press' })).toBeVisible();
  await expect(highlights.getByRole('heading', { name: 'Oldest books · Dust-bound Wisdom' })).toBeVisible();
  await expect(highlights.locator('.publication-card').first()).toContainText('2024');
  await expect(highlights.locator('.publication-card').nth(1)).toContainText('1800');
  await expect(highlights.locator('.genre-group li').first()).toContainText('Recent Book');
  await expect(highlights.locator('.genre-group li').first().locator('b')).toHaveText('2');
  await expect(highlights).toContainText('not by loans or readership');
  await expect(highlights).not.toContainText('Uncategorized');
  await expect(highlights).not.toContainText('No category');
});
