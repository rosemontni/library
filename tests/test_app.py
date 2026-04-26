import gc
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import app
from app import GeoPoint, build_search_blob, choose_best_location, haversine_miles


class AppTests(unittest.TestCase):
    def test_haversine_distance_is_reasonable(self) -> None:
        nyc = (40.7128, -74.0060)
        philly = (39.9526, -75.1652)
        distance = haversine_miles(nyc[0], nyc[1], philly[0], philly[1])
        self.assertGreater(distance, 75)
        self.assertLess(distance, 110)

    def test_search_blob_normalizes_text(self) -> None:
        blob = build_search_blob("Parable of the Sower", "Octavia Butler", "9780446675505")
        self.assertEqual(blob, "parable of the sower octavia butler 9780446675505")

    def test_exif_location_beats_browser_location(self) -> None:
        exif_location = GeoPoint(39.29, -76.61, "photo_exif", 0.99)
        browser_location = GeoPoint(39.30, -76.62, "browser_gps", 0.9)
        chosen = choose_best_location(exif_location, browser_location)
        self.assertEqual(chosen.source, "photo_exif")

    def test_mobile_contribution_endpoint_populates_central_search(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            try:
                app.initialize_database()
                server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.LibraryAtlasHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                try:
                    payload = {
                        "library_name": "Test Central Shelf",
                        "library_description": "A blue sidewalk shelf.",
                        "place_clues": ["test route"],
                        "geolocation": {
                            "latitude": 39.29,
                            "longitude": -76.61,
                            "source": "device_location",
                            "confidence": 0.96,
                            "accuracy_meters": 12,
                        },
                        "books": [
                            {
                                "title": "Parable of the Sower",
                                "author": "Octavia Butler",
                                "isbn": "",
                                "publisher": "",
                                "published_year": "",
                                "genre": "Fiction",
                                "format": "paperback",
                                "condition": "good",
                                "confidence": 0.9,
                                "notes": "mobile test",
                            }
                        ],
                    }
                    boundary = "LittleLibraryAtlasTestBoundary"
                    body = (
                        f"--{boundary}\r\n"
                        "Content-Disposition: form-data; name=\"payload\"\r\n\r\n"
                        f"{json.dumps(payload)}\r\n"
                        f"--{boundary}--\r\n"
                    ).encode("utf-8")

                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request(
                        "POST",
                        "/api/mobile/libraries",
                        body=body,
                        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                    )
                    response = connection.getresponse()
                    response_payload = json.loads(response.read().decode("utf-8"))
                    connection.close()

                    self.assertEqual(response.status, 201)
                    self.assertEqual(response_payload["counts"], {"libraries": 1, "books": 1})
                    results = app.search_books("Parable", 39.29, -76.61, 5)
                    self.assertEqual(results[0]["library"]["name"], "Test Central Shelf")
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()
                    gc.collect()
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path


if __name__ == "__main__":
    unittest.main()
