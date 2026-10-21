const { test, expect } = require('@playwright/test');
const { controlledSite, fixture } = require('./site-helpers');

test('classification numbers are searchable and show source and edition qualification', async ({ page }) => {
  const book = { ...fixture.books[0], ddc_numbers: ['635.9'], lcc_numbers: ['SB450.S65'],
    classification_status: 'matched_work', classification_sources: ['https://openlibrary.org/works/OL123W'] };
  await controlledSite(page, { data: { ...fixture, books: [book], counts: { libraries: 2, books: 1 } } });
  await page.goto('/');
  await expect(page.locator('#searchQuery')).toBeEnabled();
  for (const query of ['635.9', 'SB450.S65']) {
    await page.locator('#searchQuery').fill(query);
    await page.locator('#searchForm').getByRole('button', { name: 'Find books', exact: true }).click();
    const card = page.locator('#results .result-card');
    await expect(card).toHaveCount(1);
    await card.getByText('Book details', { exact: true }).click();
    await expect(card).toContainText('Dewey: 635.9');
    await expect(card).toContainText('LCC: SB450.S65');
    await expect(card).toContainText('edition unverified');
    await expect(card.getByRole('link', { name: 'Classification source' })).toHaveAttribute('href', 'https://openlibrary.org/works/OL123W');
  }
});
