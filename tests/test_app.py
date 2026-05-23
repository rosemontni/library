import gc
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from PIL import Image

import app
from app import GeoPoint, build_search_blob, choose_best_location, haversine_miles
from scripts.validate_public_export import validate_public_export


def gps_jpeg_bytes(latitude: float = 39.29, longitude: float = -76.61, color: str = "blue") -> bytes:
    image = Image.new("RGB", (180, 180), color)
    exif = Image.Exif()
    lat_ref = "N" if latitude >= 0 else "S"
    lon_ref = "E" if longitude >= 0 else "W"

    def dms(value: float) -> tuple[float, float, float]:
        absolute = abs(value)
        degrees = int(absolute)
        minutes_float = (absolute - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        return float(degrees), float(minutes), float(seconds)

    exif[0x8825] = {
        1: lat_ref,
        2: dms(latitude),
        3: lon_ref,
        4: dms(longitude),
    }
    output = io.BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def plain_jpeg_bytes(color: str = "gray") -> bytes:
    image = Image.new("RGB", (180, 180), color)
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


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

    def test_uploaded_photo_without_gps_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            upload_path = Path(tempdir) / "no-gps.jpg"
            upload_path.write_bytes(b"not a gps tagged jpeg")
            with self.assertRaisesRegex(ValueError, "EXIF GPS"):
                app.require_uploaded_photo_gps([{"upload_path": upload_path, "location": None}])
            self.assertFalse(upload_path.exists())

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

    def test_insert_library_rejects_new_library_without_gps(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            try:
                app.initialize_database()
                with self.assertRaisesRegex(ValueError, "GPS coordinates"):
                    app.insert_library(
                        {
                            "library_name": "Ungrounded Shelf",
                            "library_description": "Should not enter the central atlas without photo GPS.",
                            "books": [],
                        }
                    )
                self.assertEqual(app.get_counts(), {"libraries": 0, "books": 0})
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                gc.collect()

    def test_insert_library_rejects_existing_library_update_without_gps(self) -> None:
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
                        "library_name": "Grounded Shelf",
                        "geolocation": {"latitude": 39.29, "longitude": -76.61, "source": "photo_exif"},
                        "books": [],
                    }
                )

                with self.assertRaisesRegex(ValueError, "GPS coordinates"):
                    app.insert_library(
                        {
                            "library_id": library_id,
                            "library_name": "Grounded Shelf",
                            "books": [{"title": "Ungrounded Update"}],
                        }
                    )
                self.assertEqual(app.get_counts(), {"libraries": 1, "books": 0})
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                gc.collect()

    def test_public_upload_urls_are_private_by_default(self) -> None:
        original_value = os.environ.pop("CIVITAS_SERVE_UPLOADS", None)
        try:
            self.assertIsNone(app.public_upload_url("data/uploads/original.jpg"))
            os.environ["CIVITAS_SERVE_UPLOADS"] = "1"
            self.assertEqual(app.public_upload_url("data/uploads/original.jpg"), "/data/uploads/original.jpg")
        finally:
            if original_value is None:
                os.environ.pop("CIVITAS_SERVE_UPLOADS", None)
            else:
                os.environ["CIVITAS_SERVE_UPLOADS"] = original_value

    def test_public_export_validator_rejects_raw_upload_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            export_path = Path(tempdir) / "atlas-data.json"
            export_path.write_text(
                json.dumps(
                    {
                        "counts": {"libraries": 1, "books": 0},
                        "privacy": {"photos_included": False},
                        "libraries": [
                            {
                                "id": 1,
                                "name": "Unsafe Shelf",
                                "icon_url": "data/uploads/original.jpg",
                            }
                        ],
                        "books": [],
                    }
                ),
                encoding="utf-8",
            )

            errors = validate_public_export(export_path, Path(tempdir))
            self.assertTrue(any("raw upload" in error for error in errors))

    def test_public_export_validator_accepts_derived_icons(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            site_root = Path(tempdir)
            icon_dir = site_root / "library-icons"
            icon_dir.mkdir()
            (icon_dir / "csn-0001-safe-shelf.png").write_bytes(b"derived icon placeholder")
            export_path = site_root / "atlas-data.json"
            export_path.write_text(
                json.dumps(
                    {
                        "counts": {"libraries": 1, "books": 1},
                        "privacy": {"photos_included": False},
                        "libraries": [
                            {
                                "id": 1,
                                "name": "Safe Shelf",
                                "icon_url": "library-icons/csn-0001-safe-shelf.png",
                            }
                        ],
                        "books": [{"id": 1, "library_id": 1, "title": "Safe Book"}],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(validate_public_export(export_path, site_root), [])

    def test_nearby_upload_updates_existing_library_without_charter(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            try:
                app.initialize_database()
                first_id = app.insert_library(
                    {
                        "library_name": "Maple Corner Shelf",
                        "geolocation": {"latitude": 39.2900, "longitude": -76.6100, "source": "photo_exif"},
                        "books": [{"title": "First Snapshot", "genre": "Fiction"}],
                    }
                )
                second_id = app.insert_library(
                    {
                        "library_name": "Maple Corner Shelf Updated",
                        "geolocation": {"latitude": 39.2902, "longitude": -76.6102, "source": "photo_exif"},
                        "books": [{"title": "Second Snapshot", "genre": "Fiction"}],
                    }
                )

                self.assertEqual(second_id, first_id)
                self.assertEqual(app.get_counts(), {"libraries": 1, "books": 1})
                self.assertEqual(app.search_books("Second Snapshot", 39.29, -76.61, 5)[0]["library"]["id"], first_id)
                self.assertEqual(app.search_books("First Snapshot", 39.29, -76.61, 5), [])
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

    def test_export_keeps_map_marker_on_photo_gps_when_official_address_exists(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH
        original_map_output_path = app.MAP_OUTPUT_PATH
        original_pages_data_path = app.PAGES_DATA_PATH
        original_lookup = app.lookup_lfl_registration
        original_pages_env = os.environ.get("LIBRARY_PAGES_DATA_PATH")

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"
            app.MAP_OUTPUT_PATH = app.DATA_DIR / "library-map.svg"
            app.PAGES_DATA_PATH = app.DATA_DIR / "atlas-data.json"
            os.environ["LIBRARY_PAGES_DATA_PATH"] = str(app.PAGES_DATA_PATH)

            def fake_lookup(charter_number: str, latitude: float | None, longitude: float | None) -> dict[str, object]:
                return {
                    "status": "matched",
                    "charter_number": charter_number,
                    "checked_at": "2026-05-23T12:00:00+00:00",
                    "distance_miles": 0.01,
                    "street": "1000 Large Complex Drive",
                    "city": "Gaithersburg",
                    "state": "MD",
                    "postal_code": "20877",
                }

            app.lookup_lfl_registration = fake_lookup
            try:
                app.initialize_database()
                app.insert_library(
                    {
                        "library_name": "Complex Entrance Shelf",
                        "charter_number": "Charter # 123456",
                        "geolocation": {
                            "latitude": 39.123456,
                            "longitude": -77.234567,
                            "source": "photo_exif",
                            "confidence": 0.95,
                        },
                        "books": [],
                    }
                )

                pages_data = json.loads(app.PAGES_DATA_PATH.read_text(encoding="utf-8"))
                exported = pages_data["libraries"][0]
                self.assertEqual(exported["official_address"], "1000 Large Complex Drive, Gaithersburg, MD 20877")
                self.assertAlmostEqual(exported["marker_latitude"], 39.123456)
                self.assertAlmostEqual(exported["marker_longitude"], -77.234567)
                self.assertAlmostEqual(exported["latitude"], 39.123456)
                self.assertAlmostEqual(exported["longitude"], -77.234567)

                api_library = app.list_libraries()[0]
                self.assertEqual(api_library["official_address"], "1000 Large Complex Drive, Gaithersburg, MD 20877")
                self.assertAlmostEqual(api_library["marker_latitude"], 39.123456)
                self.assertAlmostEqual(api_library["marker_longitude"], -77.234567)
            finally:
                app.lookup_lfl_registration = original_lookup
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

    def test_mobile_contribution_endpoint_populates_central_search(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH
        original_map_output_path = app.MAP_OUTPUT_PATH
        original_pages_data_path = app.PAGES_DATA_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"
            app.MAP_OUTPUT_PATH = app.DATA_DIR / "library-map.svg"
            app.PAGES_DATA_PATH = app.DATA_DIR / "atlas-data.json"

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
                    parts = [
                        (
                            "payload",
                            None,
                            "application/json",
                            json.dumps(payload).encode("utf-8"),
                        ),
                        ("location_photo", "locator.jpg", "image/jpeg", gps_jpeg_bytes(color="navy")),
                        ("location_photo", "locator-2.jpg", "image/jpeg", gps_jpeg_bytes(color="green")),
                        ("additional_photos", "charter.jpg", "image/jpeg", gps_jpeg_bytes(color="purple")),
                        ("additional_photos", "side.jpg", "image/jpeg", gps_jpeg_bytes(color="orange")),
                    ]
                    chunks: list[bytes] = []
                    for name, filename, content_type, content in parts:
                        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
                        if filename:
                            chunks.append(
                                (
                                    f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                                    f"Content-Type: {content_type}\r\n\r\n"
                                ).encode("utf-8")
                            )
                        else:
                            chunks.append(f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode("utf-8"))
                        chunks.append(content)
                        chunks.append(b"\r\n")
                    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
                    body = b"".join(chunks)

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

                    self.assertEqual(response.status, 201, response_payload)
                    self.assertEqual(response_payload["counts"], {"libraries": 1, "books": 1})
                    self.assertTrue(response_payload["location_photo_url"].startswith("/data/uploads/"))
                    self.assertEqual(len(response_payload["location_photo_urls"]), 2)
                    results = app.search_books("Parable", 39.29, -76.61, 5)
                    self.assertEqual(results[0]["library"]["name"], "Test Central Shelf")
                    self.assertIsNone(results[0]["library"]["location_photo_url"])
                    with app.get_connection() as db:
                        photo_count = db.execute("SELECT COUNT(*) FROM library_photos").fetchone()[0]
                        ingestion_count = db.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
                        evidence_count = db.execute("SELECT COUNT(*) FROM photo_evidence").fetchone()[0]
                        accepted_evidence_count = db.execute(
                            "SELECT COUNT(*) FROM photo_evidence WHERE accepted = 1 AND library_id = ?",
                            (response_payload["library_id"],),
                        ).fetchone()[0]
                    self.assertEqual(photo_count, 4)
                    self.assertEqual(ingestion_count, 1)
                    self.assertEqual(evidence_count, 4)
                    self.assertEqual(accepted_evidence_count, 4)
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()
                    gc.collect()
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                app.MAP_OUTPUT_PATH = original_map_output_path
                app.PAGES_DATA_PATH = original_pages_data_path

    def test_public_search_api_accepts_zip_and_returns_rate_headers(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH
        original_map_output_path = app.MAP_OUTPUT_PATH
        original_pages_data_path = app.PAGES_DATA_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"
            app.MAP_OUTPUT_PATH = app.DATA_DIR / "library-map.svg"
            app.PAGES_DATA_PATH = app.DATA_DIR / "atlas-data.json"
            app.PUBLIC_API_RATE_LIMIT_BUCKETS.clear()

            try:
                app.initialize_database()
                app.insert_library(
                    {
                        "library_name": "Community API Shelf",
                        "library_description": "A test shelf for public API users.",
                        "geolocation": {"latitude": 39.1434, "longitude": -77.2014, "source": "photo_exif"},
                        "books": [{"title": "Parable of the Sower", "author": "Octavia Butler", "genre": "Fiction"}],
                    }
                )
                server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.LibraryAtlasHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                try:
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request("GET", "/api/v1/search?q=Parable&zip=20877&radius_miles=5&limit=5")
                    response = connection.getresponse()
                    response_payload = json.loads(response.read().decode("utf-8"))
                    remaining_header = response.getheader("X-RateLimit-Remaining")
                    connection.close()

                    self.assertEqual(response.status, 200, response_payload)
                    self.assertEqual(response_payload["api_version"], "v1")
                    self.assertEqual(response_payload["count"], 1)
                    self.assertEqual(response_payload["results"][0]["title"], "Parable of the Sower")
                    self.assertEqual(response_payload["results"][0]["library"]["csn"], "CSN-1")
                    self.assertIsNotNone(remaining_header)
                finally:
                    server.shutdown()
                    thread.join(timeout=2)
                    server.server_close()
                    gc.collect()
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                app.MAP_OUTPUT_PATH = original_map_output_path
                app.PAGES_DATA_PATH = original_pages_data_path
                app.PUBLIC_API_RATE_LIMIT_BUCKETS.clear()

    def test_public_api_rate_limit_returns_429(self) -> None:
        original_limit = app.PUBLIC_API_RATE_LIMIT_REQUESTS
        original_window = app.PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS
        app.PUBLIC_API_RATE_LIMIT_REQUESTS = 1
        app.PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS = 60
        app.PUBLIC_API_RATE_LIMIT_BUCKETS.clear()

        server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.LibraryAtlasHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            first = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            first.request("GET", "/api/v1/libraries")
            first_response = first.getresponse()
            first_response.read()
            first.close()

            second = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            second.request("GET", "/api/v1/libraries")
            second_response = second.getresponse()
            second_payload = json.loads(second_response.read().decode("utf-8"))
            retry_after = second_response.getheader("Retry-After")
            second.close()

            self.assertEqual(first_response.status, 200)
            self.assertEqual(second_response.status, 429)
            self.assertIn("Rate limit", second_payload["error"])
            self.assertIsNotNone(retry_after)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()
            app.PUBLIC_API_RATE_LIMIT_REQUESTS = original_limit
            app.PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS = original_window
            app.PUBLIC_API_RATE_LIMIT_BUCKETS.clear()
            gc.collect()

    def test_mobile_contribution_without_gps_is_rejected_and_cleaned(self) -> None:
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
                        "library_name": "No GPS Shelf",
                        "library_description": "This should be rejected because the photo has no EXIF GPS.",
                        "books": [],
                    }
                    boundary = "LittleLibraryAtlasNoGpsBoundary"
                    parts = [
                        (
                            "payload",
                            None,
                            "application/json",
                            json.dumps(payload).encode("utf-8"),
                        ),
                        ("location_photo", "stripped.jpg", "image/jpeg", plain_jpeg_bytes()),
                    ]
                    chunks: list[bytes] = []
                    for name, filename, content_type, content in parts:
                        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
                        if filename:
                            chunks.append(
                                (
                                    f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                                    f"Content-Type: {content_type}\r\n\r\n"
                                ).encode("utf-8")
                            )
                        else:
                            chunks.append(f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode("utf-8"))
                        chunks.append(content)
                        chunks.append(b"\r\n")
                    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
                    body = b"".join(chunks)

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

                    self.assertEqual(response.status, 400, response_payload)
                    self.assertIn("EXIF GPS", response_payload["error"])
                    self.assertEqual(app.get_counts(), {"libraries": 0, "books": 0})
                    self.assertEqual(list(app.UPLOADS_DIR.glob("*")), [])
                    with app.get_connection() as db:
                        self.assertEqual(db.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0], 0)
                        self.assertEqual(db.execute("SELECT COUNT(*) FROM photo_evidence").fetchone()[0], 0)
                        self.assertEqual(db.execute("SELECT COUNT(*) FROM library_photos").fetchone()[0], 0)
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

    def test_android_database_upgrade_is_non_destructive(self) -> None:
        helper_path = Path("android-app/app/src/main/java/com/rosemontni/libraryatlas/AtlasDatabaseHelper.kt")
        helper_source = helper_path.read_text(encoding="utf-8")
        upgrade_body = helper_source.split("override fun onUpgrade", 1)[1].split("companion object", 1)[0]

        self.assertNotIn("DROP TABLE", upgrade_body.upper())
        self.assertIn("migrateToVersion2", upgrade_body)
        self.assertIn("DATABASE_VERSION = 2", helper_source)

    def test_github_pages_static_smoke_test_passes(self) -> None:
        from scripts.smoke_test_pages import validate_pages_site

        self.assertEqual(validate_pages_site(Path("docs")), [])

    def test_initialize_database_records_schema_version(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            try:
                app.initialize_database()
                with app.get_connection() as db:
                    version = db.execute("SELECT version FROM schema_migrations WHERE id = 1").fetchone()["version"]
                self.assertEqual(version, app.DATABASE_SCHEMA_VERSION)
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                gc.collect()

    def test_initialize_database_rejects_newer_schema_version(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            try:
                app.initialize_database()
                with app.get_connection() as db:
                    db.execute(
                        "UPDATE schema_migrations SET version = ? WHERE id = 1",
                        (app.DATABASE_SCHEMA_VERSION + 1,),
                    )
                with self.assertRaises(RuntimeError):
                    app.initialize_database()
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                gc.collect()

    def test_initialize_database_creates_observation_layer_tables(self) -> None:
        original_data_dir = app.DATA_DIR
        original_uploads_dir = app.UPLOADS_DIR
        original_db_path = app.DB_PATH

        with tempfile.TemporaryDirectory() as tempdir:
            app.DATA_DIR = Path(tempdir)
            app.UPLOADS_DIR = app.DATA_DIR / "uploads"
            app.DB_PATH = app.DATA_DIR / "atlas.db"

            try:
                app.initialize_database()
                with app.get_connection() as db:
                    table_names = {
                        row["name"]
                        for row in db.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table'"
                        ).fetchall()
                    }
                    photo_columns = {
                        row["name"]
                        for row in db.execute("PRAGMA table_info(photo_evidence)").fetchall()
                    }
                    prediction_columns = {
                        row["name"]
                        for row in db.execute("PRAGMA table_info(model_predictions)").fetchall()
                    }
                    review_columns = {
                        row["name"]
                        for row in db.execute("PRAGMA table_info(review_decisions)").fetchall()
                    }

                self.assertTrue(
                    {
                        "ingestion_runs",
                        "photo_evidence",
                        "model_predictions",
                        "review_decisions",
                    }.issubset(table_names)
                )
                self.assertTrue({"gps_required", "accepted", "rejection_reason"}.issubset(photo_columns))
                self.assertIn("payload_json", prediction_columns)
                self.assertIn("decision", review_columns)
            finally:
                app.DATA_DIR = original_data_dir
                app.UPLOADS_DIR = original_uploads_dir
                app.DB_PATH = original_db_path
                gc.collect()


if __name__ == "__main__":
    unittest.main()
