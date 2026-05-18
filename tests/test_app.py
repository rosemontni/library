import gc
import http.client
import json
import os
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

    def test_insert_library_allows_empty_shelf(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            try:
                app.initialize_database()
                library_id = app.insert_library(
                    {
                        "library_name": "Empty Today Shelf",
                        "library_description": "A little library with no visible books in the current upload.",
                        "place_clues": ["empty shelf"],
                        "geolocation": {
                            "latitude": 39.29,
                            "longitude": -76.61,
                            "source": "test",
                            "confidence": 0.8,
                        },
                        "books": [],
                    }
                )

                self.assertGreater(library_id, 0)
                self.assertEqual(app.get_counts(), {"libraries": 1, "books": 0})
                libraries = app.list_libraries()
                self.assertEqual(libraries[0]["name"], "Empty Today Shelf")
                self.assertEqual(libraries[0]["book_count"], 0)
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                gc.collect()

    def test_newer_inventory_marks_missing_books_removed(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            try:
                app.initialize_database()
                library_id = app.insert_library(
                    {
                        "library_name": "Rotating Shelf",
                        "geolocation": {"latitude": 39.29, "longitude": -76.61, "source": "test", "confidence": 0.9},
                        "books": [
                            {
                                "title": "Old Snapshot Book",
                                "author": "Former Author",
                                "isbn": "",
                                "publisher": "",
                                "published_year": "",
                                "genre": "Fiction",
                                "format": "paperback",
                                "condition": "good",
                                "confidence": 0.9,
                                "notes": "",
                            }
                        ],
                    }
                )
                app.insert_library(
                    {
                        "library_id": library_id,
                        "library_name": "Rotating Shelf",
                        "replace_inventory": True,
                        "geolocation": {"latitude": 39.29, "longitude": -76.61, "source": "test", "confidence": 0.9},
                        "books": [
                            {
                                "title": "New Snapshot Book",
                                "author": "Current Author",
                                "isbn": "",
                                "publisher": "",
                                "published_year": "",
                                "genre": "Reference",
                                "format": "hardcover",
                                "condition": "good",
                                "confidence": 0.9,
                                "notes": "",
                            }
                        ],
                    }
                )

                self.assertEqual(app.get_counts(), {"libraries": 1, "books": 1})
                self.assertEqual(app.search_books("Old Snapshot", 39.29, -76.61, 5), [])
                self.assertEqual(app.search_books("New Snapshot", 39.29, -76.61, 5)[0]["title"], "New Snapshot Book")
                with app.get_connection() as connection:
                    rows = connection.execute("SELECT title, status, removed_at FROM books ORDER BY title").fetchall()
                statuses = {row["title"]: (row["status"], row["removed_at"]) for row in rows}
                self.assertEqual(statuses["New Snapshot Book"][0], "active")
                self.assertEqual(statuses["Old Snapshot Book"][0], "removed")
                self.assertIsNotNone(statuses["Old Snapshot Book"][1])
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                gc.collect()

    def test_charter_number_lookup_is_recorded(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH
        original_lookup = app.lookup_lfl_registration

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            def fake_lookup(charter_number: str, latitude: float | None, longitude: float | None) -> dict[str, object]:
                return {
                    "status": "matched",
                    "charter_number": charter_number,
                    "checked_at": "2026-05-17T12:00:00+00:00",
                    "distance_miles": 0.02,
                    "library_name": "Public Registry Shelf",
                    "steward_name": "Test Steward",
                    "street": "1 Test Way",
                    "city": "Gaithersburg",
                    "state": "MD",
                }

            app.lookup_lfl_registration = fake_lookup
            try:
                app.initialize_database()
                app.insert_library(
                    {
                        "library_name": "Chartered Shelf",
                        "charter_number": "Charter # 0007204",
                        "geolocation": {"latitude": 39.14, "longitude": -77.2, "source": "test", "confidence": 0.9},
                        "books": [],
                    }
                )

                with app.get_connection() as connection:
                    row = connection.execute(
                        """
                        SELECT charter_number, charter_lookup_status, charter_record_distance_miles, charter_record_json
                        FROM libraries
                        """
                    ).fetchone()

                self.assertEqual(row["charter_number"], "7204")
                self.assertEqual(row["charter_lookup_status"], "matched")
                self.assertAlmostEqual(row["charter_record_distance_miles"], 0.02)
                self.assertIn("Test Steward", row["charter_record_json"])
            finally:
                app.lookup_lfl_registration = original_lookup
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                gc.collect()

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
                        f"--{boundary}\r\n"
                        "Content-Disposition: form-data; name=\"location_photo\"; filename=\"locator.jpg\"\r\n"
                        "Content-Type: image/jpeg\r\n\r\n"
                        "fake locator image\r\n"
                        f"--{boundary}\r\n"
                        "Content-Disposition: form-data; name=\"location_photo\"; filename=\"locator-2.jpg\"\r\n"
                        "Content-Type: image/jpeg\r\n\r\n"
                        "fake second locator image\r\n"
                        f"--{boundary}\r\n"
                        "Content-Disposition: form-data; name=\"additional_photos\"; filename=\"charter.jpg\"\r\n"
                        "Content-Type: image/jpeg\r\n\r\n"
                        "fake charter label image\r\n"
                        f"--{boundary}\r\n"
                        "Content-Disposition: form-data; name=\"additional_photos\"; filename=\"side.jpg\"\r\n"
                        "Content-Type: image/jpeg\r\n\r\n"
                        "fake side image\r\n"
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
                    self.assertTrue(response_payload["location_photo_url"].startswith("/data/uploads/"))
                    self.assertEqual(len(response_payload["location_photo_urls"]), 2)
                    results = app.search_books("Parable", 39.29, -76.61, 5)
                    self.assertEqual(results[0]["library"]["name"], "Test Central Shelf")
                    self.assertTrue(results[0]["library"]["location_photo_url"].startswith("/data/uploads/"))
                    with app.get_connection() as db:
                        photo_count = db.execute("SELECT COUNT(*) FROM library_photos").fetchone()[0]
                    self.assertEqual(photo_count, 4)
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()
                    gc.collect()
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path

    def test_insert_library_refreshes_configured_readme_map(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH
        original_map_output_path = app.MAP_OUTPUT_PATH
        original_pages_data_path = app.PAGES_DATA_PATH
        original_map_env = os.environ.get("LIBRARY_MAP_PATH")
        original_pages_env = os.environ.get("LIBRARY_PAGES_DATA_PATH")

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"
            app.MAP_OUTPUT_PATH = app.DATA_DIR / "library-map.svg"
            app.PAGES_DATA_PATH = app.DATA_DIR / "atlas-data.json"
            os.environ["LIBRARY_MAP_PATH"] = str(app.MAP_OUTPUT_PATH)
            os.environ["LIBRARY_PAGES_DATA_PATH"] = str(app.PAGES_DATA_PATH)

            try:
                app.initialize_database()
                app.insert_library(
                    {
                        "library_name": "Map Hook Shelf",
                        "library_description": "A test shelf that should appear on the generated map.",
                        "place_clues": ["map hook"],
                        "geolocation": {
                            "latitude": 39.29,
                            "longitude": -76.61,
                            "source": "test",
                            "confidence": 0.9,
                            "accuracy_meters": 10,
                        },
                        "books": [
                            {
                                "title": "Map Book",
                                "author": "Cartographer",
                                "isbn": "",
                                "publisher": "",
                                "published_year": "",
                                "genre": "Reference",
                                "format": "paperback",
                                "condition": "good",
                                "confidence": 0.9,
                                "notes": "map test",
                            }
                        ],
                    }
                )

                rendered_map = app.MAP_OUTPUT_PATH.read_text(encoding="utf-8")
                self.assertIn("Map Hook Shelf", rendered_map)
                self.assertIn("1 books", rendered_map)

                pages_data = json.loads(app.PAGES_DATA_PATH.read_text(encoding="utf-8"))
                self.assertEqual(pages_data["counts"], {"libraries": 1, "books": 1})
                self.assertEqual(pages_data["libraries"][0]["name"], "Map Hook Shelf")
                self.assertEqual(pages_data["books"][0]["title"], "Map Book")
            finally:
                if original_map_env is None:
                    os.environ.pop("LIBRARY_MAP_PATH", None)
                else:
                    os.environ["LIBRARY_MAP_PATH"] = original_map_env
                if original_pages_env is None:
                    os.environ.pop("LIBRARY_PAGES_DATA_PATH", None)
                else:
                    os.environ["LIBRARY_PAGES_DATA_PATH"] = original_pages_env
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                app.MAP_OUTPUT_PATH = original_map_output_path
                app.PAGES_DATA_PATH = original_pages_data_path
                gc.collect()


if __name__ == "__main__":
    unittest.main()
