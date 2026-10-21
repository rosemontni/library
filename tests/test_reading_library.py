import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from scripts.ingest_photo import build_payload
from tests.test_app import gps_jpeg_bytes


class ReadingLibraryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.paths = patch.multiple(app, DATA_DIR=self.root, UPLOADS_DIR=self.root / 'uploads', DB_PATH=self.root / 'atlas.db')
        self.paths.start()
        app.initialize_database()
        self.location = {'latitude': 39.29, 'longitude': -76.61, 'source': 'photo_exif'}
        self.library_id = app.insert_library({
            'library_name': 'Test Shelf', 'geolocation': self.location,
            'books': [{'title': 'Original Book', 'last_seen_at': '2026-09-01'}],
        })

    def tearDown(self):
        self.paths.stop()
        gc.collect()
        self.directory.cleanup()

    def test_reading_library_survives_cli_database_search_and_exports(self):
        import json
        from scripts.export_github_pages import export_pages_data
        from scripts.render_library_map import render_library_map
        photo = self.root / 'reading.jpg'
        photo.write_bytes(gps_jpeg_bytes())
        payload = build_payload(photo, {
            'library_name': 'Read Here', 'box_type': 'reading_library',
            'books': [{'title': 'On-site Book', 'last_seen_at': '2026-10-17'}],
        }, '')
        self.assertEqual(payload['box_type'], 'reading_library')
        library_id = app.insert_library(payload)
        result = app.search_books('On-site Book', None, None, None)[0]
        self.assertEqual(result['library']['box_type'], 'reading_library')
        self.assertIn('books stay here', result['library']['box_type_label'])
        export_pages_data(app.DB_PATH, self.root/'atlas.json')
        data = json.loads((self.root/'atlas.json').read_text(encoding='utf-8'))
        library = next(x for x in data['libraries'] if x['id'] == library_id)
        self.assertEqual(library['box_type'], 'reading_library')
        self.assertIn('books stay here', library['box_type_label'])
        render_library_map(app.DB_PATH, self.root/'map.svg')
        self.assertIn('read on site; books stay here', (self.root/'map.svg').read_text(encoding='utf-8'))
