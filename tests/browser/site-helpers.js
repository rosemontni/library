const path = require('node:path');

const fixture = {
  generated_at: '2026-10-04T12:00:00+00:00',
  counts: { libraries: 2, books: 2 },
  libraries: [
    { id: 1, csn: 'CSN-0001', name: 'Maple Street Library', box_type: 'library', latitude: 39.1434, longitude: -77.2014, book_count: 2, description: 'Beside the community garden.', location_label: 'Maple Street' },
    { id: 2, csn: 'CSN-0002', name: 'Garden Pantry', box_type: 'free_pantry', latitude: 39.15, longitude: -77.21, book_count: 0 },
  ],
  books: [
    { id: 1, library_id: 1, title: 'The Secret Garden', author: 'Frances Hodgson Burnett', genre: 'Fiction', publisher: 'Example Press', published_year: '1911', format: 'paperback', confidence: 0.9 },
    { id: 2, library_id: 1, title: 'A Field Guide to Birds', author: 'Alex Reader', genre: 'Nature', confidence: 0.9 },
  ],
};

async function controlledSite(page, { data = fixture, failMap = false } = {}) {
  // Run the real Leaflet distribution, with external requests controlled.
  await page.route('https://unpkg.com/leaflet@1.9.4/dist/**', async (route) => {
    const filename = new URL(route.request().url()).pathname.split('/').pop();
    if (failMap && filename === 'leaflet.js') return route.abort();
    if (!['leaflet.js', 'leaflet.css'].includes(filename)) return route.abort();
    return route.fulfill({ path: path.join(__dirname, '../../node_modules/leaflet/dist', filename) });
  });
  await page.route('https://fonts.googleapis.com/**', route => route.fulfill({ contentType: 'text/css', body: '' }));
  await page.route('https://*.tile.openstreetmap.org/**', route => route.fulfill({
    contentType: 'image/png',
    body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64'),
  }));
  await page.route('**/local-community-boxes.json', route => route.fulfill({ json: {} }));
  await page.route('**/atlas-data.json', route => route.fulfill({ json: data }));
  await page.route('https://api.zippopotam.us/**', route => route.fulfill({
    json: { places: [{ latitude: '39.1434', longitude: '-77.2014', 'place name': 'Example Town', 'state abbreviation': 'MD' }] },
  }));
}

module.exports = { controlledSite, fixture };
