from __future__ import annotations

import base64
from collections import deque
import json
import math
import mimetypes
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from PIL import Image, ImageOps, UnidentifiedImageError


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "little_library_atlas.db"
MAP_OUTPUT_PATH = Path(os.getenv("LIBRARY_MAP_PATH", str(BASE_DIR / "assets" / "library-map.svg")))
PAGES_DATA_PATH = Path(os.getenv("LIBRARY_PAGES_DATA_PATH", str(BASE_DIR / "docs" / "atlas-data.json")))
LIBRARY_ICONS_DIR = Path(os.getenv("LIBRARY_ICONS_DIR", str(BASE_DIR / "docs" / "library-icons")))
LIBRARY_ICON_SIZE = 144
DATABASE_SCHEMA_VERSION = 2

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_RADIUS_MILES = 25.0
PUBLIC_API_VERSION = "v1"
PUBLIC_API_DEFAULT_LIMIT = 25
PUBLIC_API_MAX_LIMIT = 100
PUBLIC_API_RATE_LIMIT_REQUESTS = int(os.getenv("PUBLIC_API_RATE_LIMIT_REQUESTS", "60"))
PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS", "60"))
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_UPLOAD_FILES = 10
MAX_MULTIPART_BYTES = (MAX_IMAGE_BYTES * MAX_UPLOAD_FILES) + (2 * 1024 * 1024)
LFL_CHARTER_LOOKUP_URL = "https://appapi.littlefreelibrary.org/library/map.json?charter={charter}"
LFL_CHARTER_MATCH_RADIUS_MILES = float(os.getenv("LFL_CHARTER_MATCH_RADIUS_MILES", "0.35"))
LFL_LOOKUP_ENABLED = os.getenv("LFL_LOOKUP_ENABLED", "1") != "0"
CHARTER_NUMBER_PATTERN = re.compile(
    r"(?:little\s+free\s+library\s*)?(?:charter|chater|charter\s*number|#)\D{0,16}(\d{3,8})",
    re.IGNORECASE,
)

NONFICTION_MARKERS = (
    "history",
    "biography",
    "travel",
    "health",
    "nutrition",
    "gardening",
    "garden",
    "houseplants",
    "landscape",
    "herbs",
    "fitness",
    "yoga",
    "careers",
)
FICTION_MARKERS = ("fiction", "film", "dvd")
CATEGORY_MARKERS = {
    "kids": ("children", "middle grade", "young adult", "bilingual", "mythology"),
    "gardening": ("gardening", "garden", "houseplants", "landscape", "herbs", "greenhouse", "plants"),
    "travel": ("travel", "paris", "italy", "florence", "tuscany"),
    "history": ("history", "biography", "civil war", "lincoln", "appomattox"),
    "wellness": ("health", "nutrition", "fitness", "yoga"),
    "media": ("dvd", "film"),
}

LOCAL_ZIP_CENTROIDS: dict[str, dict[str, Any]] = {
    "20001": {"latitude": 38.9101, "longitude": -77.0171, "label": "Washington, DC 20001"},
    "20002": {"latitude": 38.9057, "longitude": -76.9845, "label": "Washington, DC 20002"},
    "20003": {"latitude": 38.884, "longitude": -76.994, "label": "Washington, DC 20003"},
    "20007": {"latitude": 38.9146, "longitude": -77.0742, "label": "Washington, DC 20007"},
    "20740": {"latitude": 38.996, "longitude": -76.929, "label": "College Park, MD 20740"},
    "20814": {"latitude": 38.9907, "longitude": -77.1003, "label": "Bethesda, MD 20814"},
    "20815": {"latitude": 38.9834, "longitude": -77.0789, "label": "Chevy Chase, MD 20815"},
    "20817": {"latitude": 39.0007, "longitude": -77.1547, "label": "Bethesda, MD 20817"},
    "20850": {"latitude": 39.0891, "longitude": -77.1837, "label": "Rockville, MD 20850"},
    "20852": {"latitude": 39.0497, "longitude": -77.1209, "label": "North Bethesda, MD 20852"},
    "20854": {"latitude": 39.0384, "longitude": -77.2003, "label": "Potomac, MD 20854"},
    "20877": {"latitude": 39.1434, "longitude": -77.2014, "label": "Gaithersburg, MD 20877"},
    "20878": {"latitude": 39.1148, "longitude": -77.2469, "label": "Gaithersburg, MD 20878"},
    "20879": {"latitude": 39.1699, "longitude": -77.1696, "label": "Gaithersburg, MD 20879"},
    "20895": {"latitude": 39.0297, "longitude": -77.0764, "label": "Kensington, MD 20895"},
    "20901": {"latitude": 39.0219, "longitude": -77.0077, "label": "Silver Spring, MD 20901"},
    "20902": {"latitude": 39.0438, "longitude": -77.0458, "label": "Silver Spring, MD 20902"},
    "20910": {"latitude": 38.9987, "longitude": -77.033, "label": "Silver Spring, MD 20910"},
    "20912": {"latitude": 38.9807, "longitude": -76.9897, "label": "Takoma Park, MD 20912"},
    "21044": {"latitude": 39.207, "longitude": -76.883, "label": "Columbia, MD 21044"},
    "21201": {"latitude": 39.2953, "longitude": -76.6181, "label": "Baltimore, MD 21201"},
    "22201": {"latitude": 38.8865, "longitude": -77.095, "label": "Arlington, VA 22201"},
    "22202": {"latitude": 38.8564, "longitude": -77.0539, "label": "Arlington, VA 22202"},
    "22203": {"latitude": 38.8735, "longitude": -77.1175, "label": "Arlington, VA 22203"},
    "22204": {"latitude": 38.8613, "longitude": -77.0985, "label": "Arlington, VA 22204"},
    "22205": {"latitude": 38.8836, "longitude": -77.139, "label": "Arlington, VA 22205"},
    "22301": {"latitude": 38.8197, "longitude": -77.0584, "label": "Alexandria, VA 22301"},
}
PUBLIC_API_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}
PUBLIC_API_RATE_LIMIT_LOCK = threading.Lock()

OPENAI_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")

BOOK_FIELDS = [
    "title",
    "author",
    "isbn",
    "publisher",
    "published_year",
    "genre",
    "format",
    "condition",
    "confidence",
    "notes",
]

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "library_name_suggestion",
        "library_description",
        "photo_summary",
        "place_clues",
        "charter_number",
        "books",
    ],
    "properties": {
        "library_name_suggestion": {"type": "string"},
        "library_description": {"type": "string"},
        "photo_summary": {"type": "string"},
        "place_clues": {"type": "array", "items": {"type": "string"}},
        "charter_number": {"type": "string"},
        "books": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": BOOK_FIELDS,
                "properties": {
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "isbn": {"type": "string"},
                    "publisher": {"type": "string"},
                    "published_year": {"type": "string"},
                    "genre": {"type": "string"},
                    "format": {"type": "string"},
                    "condition": {"type": "string"},
                    "confidence": {"type": "number"},
                    "notes": {"type": "string"},
                },
            },
        },
    },
}

ANALYSIS_SYSTEM_PROMPT = """You are an assistant that extracts structured data from photos of small public little libraries on sidewalks.

Return JSON only.
Do not invent books that are not visible.
If you are unsure, keep a field blank and lower the confidence.
Only include books that are visibly present in the photo.
Do not guess an ISBN unless it is clearly visible or highly reliable from the exact edition clues.
Use concise phrases.
"""

ANALYSIS_USER_PROMPT = """Analyze these photo(s) of one little library.

Return JSON with:
- library_name_suggestion: a short descriptive nickname for this library
- library_description: one or two sentences describing the library setup and condition
- photo_summary: a plain-language summary of what is in the image
- place_clues: visible clues such as street signs, murals, house numbers, nearby businesses, or neighborhood hints
- charter_number: the Little Free Library charter number if visible, usually near a "Charter #" label; otherwise blank
- books: the visible books with metadata fields title, author, isbn, publisher, published_year, genre, format, condition, confidence, notes

If no books are readable, return an empty books array.
Confidence must be between 0 and 1.
"""


@dataclass
class GeoPoint:
    latitude: float
    longitude: float
    source: str
    confidence: float
    accuracy_meters: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "source": self.source,
            "confidence": self.confidence,
            "accuracy_meters": self.accuracy_meters,
        }


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        should_suppress = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return bool(should_suppress)


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_ICONS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_schema_version(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    row = connection.execute("SELECT version FROM schema_migrations WHERE id = 1").fetchone()
    if row is None:
        connection.execute(
            "INSERT INTO schema_migrations (id, version) VALUES (1, ?)",
            (DATABASE_SCHEMA_VERSION,),
        )
        return

    current_version = int(row["version"])
    if current_version > DATABASE_SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {current_version} is newer than this app supports "
            f"({DATABASE_SCHEMA_VERSION})."
        )
    if current_version < DATABASE_SCHEMA_VERSION:
        connection.execute(
            """
            UPDATE schema_migrations
            SET version = ?, applied_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (DATABASE_SCHEMA_VERSION,),
        )


def initialize_database() -> None:
    ensure_directories()
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS libraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                latitude REAL,
                longitude REAL,
                location_source TEXT NOT NULL,
                location_confidence REAL NOT NULL DEFAULT 0,
                browser_accuracy_meters REAL,
                photo_path TEXT,
                books_photo_path TEXT,
                location_photo_path TEXT,
                icon_path TEXT,
                charter_number TEXT,
                charter_lookup_status TEXT,
                charter_record_checked_at TEXT,
                charter_record_distance_miles REAL,
                charter_record_json TEXT,
                place_clues TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                author TEXT,
                isbn TEXT,
                publisher TEXT,
                published_year TEXT,
                genre TEXT,
                format TEXT,
                condition TEXT,
                confidence REAL,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                first_seen_at TEXT,
                last_seen_at TEXT,
                removed_at TEXT,
                search_blob TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS library_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                photo_path TEXT NOT NULL,
                original_filename TEXT,
                content_type TEXT,
                latitude REAL,
                longitude REAL,
                location_source TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL DEFAULT 'local',
                status TEXT NOT NULL DEFAULT 'draft',
                contributor_contact TEXT,
                submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT,
                model_name TEXT,
                prompt_version TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS photo_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE SET NULL,
                library_id INTEGER REFERENCES libraries(id) ON DELETE SET NULL,
                role TEXT NOT NULL,
                photo_path TEXT NOT NULL,
                original_filename TEXT,
                content_type TEXT,
                latitude REAL,
                longitude REAL,
                location_source TEXT,
                gps_required INTEGER NOT NULL DEFAULT 1,
                accepted INTEGER NOT NULL DEFAULT 1,
                rejection_reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS model_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE CASCADE,
                photo_evidence_id INTEGER REFERENCES photo_evidence(id) ON DELETE SET NULL,
                prediction_type TEXT NOT NULL,
                model_name TEXT,
                prompt_version TEXT,
                payload_json TEXT NOT NULL,
                confidence REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS review_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE CASCADE,
                reviewer TEXT,
                decision TEXT NOT NULL,
                target_type TEXT,
                target_id INTEGER,
                notes TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            """
        )
        ensure_column(connection, "libraries", "books_photo_path", "TEXT")
        ensure_column(connection, "libraries", "location_photo_path", "TEXT")
        ensure_column(connection, "libraries", "icon_path", "TEXT")
        ensure_column(connection, "libraries", "charter_number", "TEXT")
        ensure_column(connection, "libraries", "charter_lookup_status", "TEXT")
        ensure_column(connection, "libraries", "charter_record_checked_at", "TEXT")
        ensure_column(connection, "libraries", "charter_record_distance_miles", "REAL")
        ensure_column(connection, "libraries", "charter_record_json", "TEXT")
        ensure_column(connection, "books", "status", "TEXT NOT NULL DEFAULT 'active'")
        ensure_column(connection, "books", "first_seen_at", "TEXT")
        ensure_column(connection, "books", "last_seen_at", "TEXT")
        ensure_column(connection, "books", "removed_at", "TEXT")
        connection.execute("UPDATE books SET status = 'active' WHERE status IS NULL OR status = ''")
        connection.execute("UPDATE books SET first_seen_at = created_at WHERE first_seen_at IS NULL")
        connection.execute("UPDATE books SET last_seen_at = created_at WHERE last_seen_at IS NULL")
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_books_library_id ON books(library_id);
            CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
            CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
            CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);
            CREATE INDEX IF NOT EXISTS idx_libraries_coords ON libraries(latitude, longitude);
            CREATE INDEX IF NOT EXISTS idx_libraries_charter ON libraries(charter_number);
            CREATE INDEX IF NOT EXISTS idx_library_photos_library_id ON library_photos(library_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_library_photos_unique_path
                ON library_photos(library_id, role, photo_path);
            CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status ON ingestion_runs(status);
            CREATE INDEX IF NOT EXISTS idx_photo_evidence_run_id ON photo_evidence(ingestion_run_id);
            CREATE INDEX IF NOT EXISTS idx_photo_evidence_library_id ON photo_evidence(library_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_photo_evidence_unique_path
                ON photo_evidence(photo_path);
            CREATE INDEX IF NOT EXISTS idx_model_predictions_run_id ON model_predictions(ingestion_run_id);
            CREATE INDEX IF NOT EXISTS idx_review_decisions_run_id ON review_decisions(ingestion_run_id);
            """
        )
        ensure_schema_version(connection)


def should_refresh_library_map() -> bool:
    if os.getenv("LITTLE_LIBRARY_DISABLE_MAP_RENDER") == "1":
        return False
    if "LIBRARY_MAP_PATH" in os.environ:
        return True
    return DB_PATH.resolve() == (DATA_DIR / "little_library_atlas.db").resolve()


def refresh_library_map() -> None:
    if not should_refresh_library_map():
        return

    try:
        from scripts.render_library_map import render_library_map

        render_library_map(DB_PATH, MAP_OUTPUT_PATH)
    except Exception as error:
        print(f"Warning: library map refresh failed: {error}")


def should_refresh_pages_data() -> bool:
    if os.getenv("LITTLE_LIBRARY_DISABLE_PAGES_EXPORT") == "1":
        return False
    if "LIBRARY_PAGES_DATA_PATH" in os.environ:
        return True
    return DB_PATH.resolve() == (DATA_DIR / "little_library_atlas.db").resolve()


def refresh_pages_data() -> None:
    if not should_refresh_pages_data():
        return

    try:
        from scripts.export_github_pages import export_pages_data

        export_pages_data(DB_PATH, PAGES_DATA_PATH)
    except Exception as error:
        print(f"Warning: GitHub Pages data export failed: {error}")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9\s-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_search_blob(*parts: Any) -> str:
    normalized = [normalize_text(part) for part in parts if normalize_text(part)]
    return " ".join(normalized)


def to_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_zip_code(value: Any) -> str:
    match = re.match(r"^(\d{5})(?:-\d{4})?$", str(value or "").strip())
    return match.group(1) if match else ""


def query_value(params: dict[str, list[str]], *names: str, default: str = "") -> str:
    for name in names:
        values = params.get(name)
        if values and values[0] not in (None, ""):
            return str(values[0]).strip()
    return default


def bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    parsed = to_float(value)
    if parsed is None:
        parsed = default
    return max(minimum, min(maximum, parsed))


def resolve_public_api_location(params: dict[str, list[str]]) -> tuple[float | None, float | None, str]:
    latitude = to_float(query_value(params, "lat", "latitude"))
    longitude = to_float(query_value(params, "lon", "lng", "longitude"))
    if latitude is not None and longitude is not None:
        return latitude, longitude, "coordinates"

    zip_code = normalize_zip_code(query_value(params, "zip", "zipcode", "postal_code"))
    if not zip_code:
        return None, None, ""

    centroid = LOCAL_ZIP_CENTROIDS.get(zip_code)
    if not centroid:
        raise ValueError(
            f"ZIP code {zip_code} is not in the built-in local centroid table yet. "
            "Use latitude and longitude for broader coverage."
        )
    return float(centroid["latitude"]), float(centroid["longitude"]), str(centroid["label"])


def check_public_api_rate_limit(client_key: str) -> dict[str, Any]:
    limit = PUBLIC_API_RATE_LIMIT_REQUESTS
    window_seconds = PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS
    if limit <= 0 or window_seconds <= 0:
        return {"allowed": True, "limit": limit, "remaining": -1, "reset_seconds": 0, "retry_after": 0}

    now = time.monotonic()
    window_start = now - window_seconds
    with PUBLIC_API_RATE_LIMIT_LOCK:
        bucket = PUBLIC_API_RATE_LIMIT_BUCKETS.setdefault(client_key, deque())
        while bucket and bucket[0] <= window_start:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, math.ceil(bucket[0] + window_seconds - now))
            return {
                "allowed": False,
                "limit": limit,
                "remaining": 0,
                "reset_seconds": retry_after,
                "retry_after": retry_after,
            }

        bucket.append(now)
        reset_seconds = max(1, math.ceil(bucket[0] + window_seconds - now))
        return {
            "allowed": True,
            "limit": limit,
            "remaining": max(0, limit - len(bucket)),
            "reset_seconds": reset_seconds,
            "retry_after": 0,
        }


def rate_limit_headers(rate_limit: dict[str, Any]) -> dict[str, str]:
    headers = {
        "X-RateLimit-Limit": str(rate_limit["limit"]),
        "X-RateLimit-Remaining": str(rate_limit["remaining"]),
        "X-RateLimit-Reset": str(rate_limit["reset_seconds"]),
    }
    if rate_limit.get("retry_after"):
        headers["Retry-After"] = str(rate_limit["retry_after"])
    return headers


def clamp_confidence(value: Any) -> float:
    numeric = to_float(value)
    if numeric is None:
        return 0.0
    return max(0.0, min(1.0, numeric))


def create_ingestion_run(
    connection: sqlite3.Connection,
    *,
    source: str = "local",
    status: str = "draft",
    contributor_contact: str = "",
    model_name: str = "",
    prompt_version: str = "",
    notes: str = "",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO ingestion_runs (
            source,
            status,
            contributor_contact,
            model_name,
            prompt_version,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(source or "local").strip() or "local",
            str(status or "draft").strip() or "draft",
            str(contributor_contact or "").strip() or None,
            str(model_name or "").strip() or None,
            str(prompt_version or "").strip() or None,
            str(notes or "").strip() or None,
        ),
    )
    return int(cursor.lastrowid)


def complete_ingestion_run(connection: sqlite3.Connection, ingestion_run_id: int, status: str = "processed") -> None:
    connection.execute(
        """
        UPDATE ingestion_runs
        SET status = ?, processed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (str(status or "processed").strip() or "processed", ingestion_run_id),
    )


def photo_evidence_location_values(photo: dict[str, Any]) -> tuple[float | None, float | None, str]:
    location = photo.get("location")
    if isinstance(location, GeoPoint):
        return location.latitude, location.longitude, location.source
    if isinstance(location, dict):
        return to_float(location.get("latitude")), to_float(location.get("longitude")), str(location.get("source") or "")
    return None, None, ""


def record_photo_evidence(
    connection: sqlite3.Connection,
    *,
    ingestion_run_id: int,
    library_id: int | None,
    photos: list[dict[str, Any]],
    accepted: bool = True,
    rejection_reason: str = "",
) -> int:
    recorded = 0
    for photo in photos:
        photo_path = str(photo.get("photo_path") or "").strip()
        if not photo_path:
            continue
        latitude, longitude, location_source = photo_evidence_location_values(photo)
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO photo_evidence (
                ingestion_run_id,
                library_id,
                role,
                photo_path,
                original_filename,
                content_type,
                latitude,
                longitude,
                location_source,
                gps_required,
                accepted,
                rejection_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ingestion_run_id,
                library_id,
                str(photo.get("role") or "photo").strip() or "photo",
                photo_path,
                str(photo.get("original_filename") or "").strip() or None,
                str(photo.get("content_type") or "").strip() or None,
                latitude,
                longitude,
                location_source.strip() or None,
                1,
                1 if accepted else 0,
                str(rejection_reason or "").strip() or None,
            ),
        )
        if cursor.rowcount:
            recorded += 1
    return recorded


def sanitize_book(raw_book: dict[str, Any]) -> dict[str, Any]:
    book: dict[str, Any] = {}
    for field in BOOK_FIELDS:
        if field == "confidence":
            book[field] = clamp_confidence(raw_book.get(field))
        else:
            book[field] = str(raw_book.get(field, "") or "").strip()
    return book


def book_identity(book: dict[str, Any] | sqlite3.Row) -> str:
    isbn = normalize_text(book["isbn"] if isinstance(book, sqlite3.Row) else book.get("isbn"))
    if isbn:
        return f"isbn:{isbn}"
    title = normalize_text(book["title"] if isinstance(book, sqlite3.Row) else book.get("title"))
    author = normalize_text(book["author"] if isinstance(book, sqlite3.Row) else book.get("author"))
    return f"title:{title}|author:{author}"


def normalize_charter_number(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D+", "", text)
    return digits.lstrip("0") or digits


def extract_charter_number_from_text(*values: Any) -> str:
    text = " ".join(str(value or "") for value in values)
    match = CHARTER_NUMBER_PATTERN.search(text)
    return normalize_charter_number(match.group(1)) if match else ""


def parse_json_object(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        return raw_value
    if not raw_value:
        return {}
    try:
        parsed = json.loads(str(raw_value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def format_official_address(raw_value: Any) -> str:
    record = parse_json_object(raw_value)
    if record.get("status") != "matched":
        return ""

    street = str(record.get("street") or "").strip()
    city = str(record.get("city") or "").strip()
    state = str(record.get("state") or "").strip()
    postal_code = str(record.get("postal_code") or "").strip()
    country = str(record.get("country") or "").strip()

    city_line = ", ".join(part for part in [city, state] if part)
    if postal_code:
        city_line = f"{city_line} {postal_code}".strip()

    parts = [part for part in [street, city_line] if part]
    if country and country.upper() not in {"US", "USA", "UNITED STATES"}:
        parts.append(country)
    return ", ".join(parts)


def normalize_photo_paths(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                value = parsed
            else:
                value = [value]
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        value = [value]

    paths: list[str] = []
    for item in value:
        path = str(item or "").strip().lstrip("/")
        if path and path not in paths:
            paths.append(path)
    return paths


def file_list(files: dict[str, list[dict[str, Any]]], *names: str) -> list[dict[str, Any]]:
    uploads: list[dict[str, Any]] = []
    for name in names:
        value = files.get(name) or []
        uploads.extend(value if isinstance(value, list) else [value])
    return [upload for upload in uploads if upload and upload.get("data")]


def first_file(files: dict[str, list[dict[str, Any]]], *names: str) -> dict[str, Any] | None:
    uploads = file_list(files, *names)
    return uploads[0] if uploads else None


def unique_upload_path(filename: str | None) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = Path(filename or "capture.jpg").suffix.lower() or ".jpg"
    safe_suffix = suffix if len(suffix) <= 8 else ".jpg"
    return UPLOADS_DIR / f"{timestamp}-{uuid.uuid4().hex}{safe_suffix}"


def save_uploaded_image(upload: dict[str, Any]) -> tuple[Path, str, str]:
    image_bytes = upload.get("data") or b""
    if not image_bytes:
        raise ValueError("The uploaded photo is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Please upload an image smaller than 25 MB.")

    upload_path = unique_upload_path(upload.get("filename"))
    upload_path.write_bytes(image_bytes)
    try:
        photo_path = upload_path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        photo_path = f"data/uploads/{upload_path.name}"
    return upload_path, photo_path, f"/{photo_path}"


def save_uploaded_images(uploads: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for upload in uploads:
        upload_path, photo_path, photo_url = save_uploaded_image(upload)
        location = extract_exif_gps(upload.get("data") or b"")
        if location:
            location.source = f"{role}_exif"
        saved.append(
            {
                "role": role,
                "upload_path": upload_path,
                "photo_path": photo_path,
                "photo_url": photo_url,
                "original_filename": upload.get("filename") or upload_path.name,
                "content_type": upload.get("content_type") or mimetypes.guess_type(upload_path.name)[0] or "",
                "location": location,
                "data": upload.get("data") or b"",
            }
        )
    return saved


def photo_records_from_saved(saved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in saved:
        location = item.get("location")
        records.append(
            {
                "role": item.get("role") or "photo",
                "photo_path": item.get("photo_path") or "",
                "original_filename": item.get("original_filename") or "",
                "content_type": item.get("content_type") or "",
                "location": location.to_dict() if isinstance(location, GeoPoint) else {},
            }
        )
    return records


def remove_saved_uploads(saved: list[dict[str, Any]]) -> None:
    for item in saved:
        upload_path = item.get("upload_path")
        if isinstance(upload_path, Path):
            try:
                upload_path.unlink(missing_ok=True)
            except OSError:
                pass


def require_uploaded_photo_gps(saved: list[dict[str, Any]]) -> dict[str, Any]:
    for item in saved:
        if isinstance(item.get("location"), GeoPoint):
            return item
    remove_saved_uploads(saved)
    raise ValueError(
        "Rejected: at least one uploaded photo must include EXIF GPS metadata. "
        "Enable location for the camera and upload the original GPS-tagged photo."
    )


def require_new_library_location(latitude: float | None, longitude: float | None) -> None:
    if latitude is None or longitude is None:
        raise ValueError(
            "Rejected: new libraries must include GPS coordinates from an accepted photo. "
            "Upload the original GPS-tagged photo instead of a screenshot or stripped copy."
        )


def require_new_library_name(library_name: str) -> None:
    if not library_name:
        raise ValueError("Rejected: new libraries must include a descriptive library name.")


def photo_url_from_path(photo_path: Any) -> str | None:
    path = str(photo_path or "").strip().lstrip("/")
    return f"/{path.replace(os.sep, '/')}" if path else None


def public_upload_url(photo_path: Any) -> str | None:
    if os.getenv("CIVITAS_SERVE_UPLOADS") != "1":
        return None
    return photo_url_from_path(photo_path)


def public_icon_path(icon_path: Any) -> str | None:
    path = str(icon_path or "").strip().lstrip("/").replace("\\", "/")
    return f"/{path}" if path else None


def slugify_filename(value: str, fallback: str = "library") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48].strip("-") or fallback


def icon_filename(library_id: int, library_name: str) -> str:
    return f"csn-{library_id:04d}-{slugify_filename(library_name)}.png"


def source_photo_to_path(photo_path: Any) -> Path | None:
    normalized = str(photo_path or "").strip().lstrip("/").replace("\\", "/")
    if not normalized:
        return None
    candidate = (BASE_DIR / normalized).resolve()
    try:
        candidate.relative_to(BASE_DIR.resolve())
    except ValueError:
        return None
    return candidate


def create_library_icon(library_id: int, library_name: str, source_photo_path: Any) -> str:
    source = source_photo_to_path(source_photo_path)
    if not source or not source.exists():
        return ""

    ensure_directories()
    output = LIBRARY_ICONS_DIR / icon_filename(library_id, library_name)
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            resample = getattr(Image, "Resampling", Image).LANCZOS
            icon = ImageOps.fit(image, (LIBRARY_ICON_SIZE, LIBRARY_ICON_SIZE), method=resample)
            icon.save(output, format="PNG", optimize=True)
    except (OSError, UnidentifiedImageError):
        return ""

    return f"library-icons/{output.name}"


def select_icon_source_photo(payload: dict[str, Any], photo_path: str) -> str:
    return first_photo_path(
        payload.get("icon_source_photo_path"),
        payload.get("icon_source_photo_paths"),
        payload.get("location_photo_path"),
        payload.get("location_photo_paths"),
        payload.get("books_photo_path"),
        payload.get("books_photo_paths"),
        photo_path,
        payload.get("photo_path"),
        payload.get("photo_paths"),
    )


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8"))


def parse_multipart_form_data(handler: BaseHTTPRequestHandler) -> tuple[dict[str, str], dict[str, list[dict[str, Any]]]]:
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("Expected multipart/form-data")

    content_length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(content_length)
    if len(body) > MAX_MULTIPART_BYTES:
        raise ValueError("Upload is too large")

    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(header + body)

    fields: dict[str, str] = {}
    files: dict[str, list[dict[str, Any]]] = {}

    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue

        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            if sum(len(items) for items in files.values()) >= MAX_UPLOAD_FILES:
                raise ValueError(f"Upload at most {MAX_UPLOAD_FILES} photos at a time.")
            files.setdefault(name, []).append(
                {
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "data": payload,
                }
            )
        else:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8").strip()

    return fields, files


TYPE_SIZES = {
    1: 1,  # BYTE
    2: 1,  # ASCII
    3: 2,  # SHORT
    4: 4,  # LONG
    5: 8,  # RATIONAL
    7: 1,  # UNDEFINED
    9: 4,  # SLONG
    10: 8,  # SRATIONAL
}


def _read_uint16(data: bytes, offset: int, endian: str) -> int:
    return int.from_bytes(data[offset : offset + 2], endian)


def _read_uint32(data: bytes, offset: int, endian: str) -> int:
    return int.from_bytes(data[offset : offset + 4], endian)


def _read_ifd_entries(data: bytes, base_offset: int, ifd_offset: int, endian: str) -> dict[int, tuple[int, int, bytes]]:
    start = base_offset + ifd_offset
    entry_count = _read_uint16(data, start, endian)
    entries: dict[int, tuple[int, int, bytes]] = {}
    cursor = start + 2

    for _ in range(entry_count):
        tag = _read_uint16(data, cursor, endian)
        field_type = _read_uint16(data, cursor + 2, endian)
        count = _read_uint32(data, cursor + 4, endian)
        value_bytes = data[cursor + 8 : cursor + 12]
        entries[tag] = (field_type, count, value_bytes)
        cursor += 12

    return entries


def _read_ifd_value(
    data: bytes,
    base_offset: int,
    field_type: int,
    count: int,
    value_bytes: bytes,
    endian: str,
) -> Any:
    type_size = TYPE_SIZES.get(field_type)
    if not type_size:
        return None

    total_size = type_size * count
    if total_size <= 4:
        raw = value_bytes[:total_size]
    else:
        pointed_offset = int.from_bytes(value_bytes, endian)
        raw = data[base_offset + pointed_offset : base_offset + pointed_offset + total_size]

    if field_type == 2:
        return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
    if field_type in {1, 7}:
        return tuple(raw)
    if field_type == 3:
        return tuple(
            int.from_bytes(raw[index : index + 2], endian) for index in range(0, len(raw), 2)
        )
    if field_type == 4:
        return tuple(
            int.from_bytes(raw[index : index + 4], endian) for index in range(0, len(raw), 4)
        )
    if field_type == 5:
        values = []
        for index in range(0, len(raw), 8):
            numerator = int.from_bytes(raw[index : index + 4], endian)
            denominator = int.from_bytes(raw[index + 4 : index + 8], endian)
            values.append((numerator / denominator) if denominator else 0.0)
        return tuple(values)
    if field_type == 9:
        values = []
        for index in range(0, len(raw), 4):
            values.append(int.from_bytes(raw[index : index + 4], endian, signed=True))
        return tuple(values)
    if field_type == 10:
        values = []
        for index in range(0, len(raw), 8):
            numerator = int.from_bytes(raw[index : index + 4], endian, signed=True)
            denominator = int.from_bytes(raw[index + 4 : index + 8], endian, signed=True)
            values.append((numerator / denominator) if denominator else 0.0)
        return tuple(values)
    return None


def _dms_to_decimal(parts: tuple[float, float, float], ref: str) -> float:
    degrees, minutes, seconds = parts
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in {"S", "W"}:
        return -decimal
    return decimal


def extract_exif_gps(image_bytes: bytes) -> GeoPoint | None:
    if not image_bytes.startswith(b"\xff\xd8"):
        return None

    offset = 2
    while offset + 4 <= len(image_bytes):
        if image_bytes[offset] != 0xFF:
            break

        marker = image_bytes[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue

        segment_length = int.from_bytes(image_bytes[offset : offset + 2], "big")
        segment_data_start = offset + 2
        segment_data_end = segment_data_start + segment_length - 2
        segment_data = image_bytes[segment_data_start:segment_data_end]

        if marker == 0xE1 and segment_data.startswith(b"Exif\x00\x00"):
            exif = segment_data[6:]
            if len(exif) < 8:
                return None

            byte_order = exif[:2]
            if byte_order == b"II":
                endian = "little"
            elif byte_order == b"MM":
                endian = "big"
            else:
                return None

            tiff_magic = _read_uint16(exif, 2, endian)
            if tiff_magic != 42:
                return None

            ifd0_offset = _read_uint32(exif, 4, endian)
            if ifd0_offset >= len(exif):
                return None

            ifd0 = _read_ifd_entries(exif, 0, ifd0_offset, endian)
            gps_tag = ifd0.get(0x8825)
            if not gps_tag:
                return None

            gps_offset_value = _read_ifd_value(exif, 0, *gps_tag, endian)
            if not gps_offset_value:
                return None

            gps_offset = int(gps_offset_value[0] if isinstance(gps_offset_value, tuple) else gps_offset_value)
            gps_ifd = _read_ifd_entries(exif, 0, gps_offset, endian)

            lat_ref = gps_ifd.get(1)
            lat_val = gps_ifd.get(2)
            lon_ref = gps_ifd.get(3)
            lon_val = gps_ifd.get(4)

            if not all([lat_ref, lat_val, lon_ref, lon_val]):
                return None

            latitude_ref = str(_read_ifd_value(exif, 0, *lat_ref, endian) or "").strip().upper()
            longitude_ref = str(_read_ifd_value(exif, 0, *lon_ref, endian) or "").strip().upper()
            latitude_parts = _read_ifd_value(exif, 0, *lat_val, endian)
            longitude_parts = _read_ifd_value(exif, 0, *lon_val, endian)

            if not latitude_ref or not longitude_ref:
                return None
            if not latitude_parts or not longitude_parts:
                return None
            if len(latitude_parts) < 3 or len(longitude_parts) < 3:
                return None

            return GeoPoint(
                latitude=_dms_to_decimal(latitude_parts[:3], latitude_ref),
                longitude=_dms_to_decimal(longitude_parts[:3], longitude_ref),
                source="photo_exif",
                confidence=0.99,
                accuracy_meters=None,
            )

        offset = segment_data_end

    return None


def choose_best_location(*locations: GeoPoint | None) -> GeoPoint | None:
    for location in locations:
        if location:
            return location
    return None


def build_browser_location(fields: dict[str, str]) -> GeoPoint | None:
    latitude = to_float(fields.get("browser_latitude"))
    longitude = to_float(fields.get("browser_longitude"))
    accuracy = to_float(fields.get("browser_accuracy_meters"))

    if latitude is None or longitude is None:
        return None

    confidence = 0.92
    if accuracy is not None:
        if accuracy <= 10:
            confidence = 0.97
        elif accuracy <= 50:
            confidence = 0.94
        elif accuracy <= 250:
            confidence = 0.9
        else:
            confidence = 0.8

    return GeoPoint(
        latitude=latitude,
        longitude=longitude,
        source="browser_gps",
        confidence=confidence,
        accuracy_meters=accuracy,
    )


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.7613

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_miles * c


def fetch_public_json(url: str, timeout: int = 8) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "CivitasLibrary/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def summarize_lfl_record(record: dict[str, Any], distance_miles: float | None, status: str) -> dict[str, Any]:
    latitude = to_float(record.get("Library_Geolocation__Latitude__s"))
    longitude = to_float(record.get("Library_Geolocation__Longitude__s"))
    return {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "distance_miles": distance_miles,
        "lfl_id": record.get("id"),
        "official_charter_number": normalize_charter_number(record.get("Official_Charter_Number__c")),
        "library_name": record.get("Library_Name__c") or record.get("List_As_Name__c") or "",
        "steward_name": record.get("Primary_Steward_s_Name__c") or "",
        "street": record.get("Street__c") or "",
        "city": record.get("City__c") or "",
        "state": record.get("State_Province_Region__c") or "",
        "postal_code": record.get("Postal_Zip_Code__c") or "",
        "country": record.get("Country__c") or "",
        "latitude": latitude,
        "longitude": longitude,
        "record_url": record.get("url") or "",
    }


def lookup_lfl_registration(
    charter_number: str,
    latitude: float | None,
    longitude: float | None,
) -> dict[str, Any]:
    charter = normalize_charter_number(charter_number)
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not charter:
        return {"status": "no_charter_number", "checked_at": checked_at}
    if not LFL_LOOKUP_ENABLED:
        return {"status": "lookup_disabled", "charter_number": charter, "checked_at": checked_at}

    try:
        payload = fetch_public_json(LFL_CHARTER_LOOKUP_URL.format(charter=quote(charter)))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        return {
            "status": "lookup_error",
            "charter_number": charter,
            "checked_at": checked_at,
            "error": str(error),
        }

    records = payload.get("libraries") if isinstance(payload, dict) else []
    if not records:
        return {"status": "not_found", "charter_number": charter, "checked_at": checked_at}

    record = records[0]
    record_latitude = to_float(record.get("Library_Geolocation__Latitude__s"))
    record_longitude = to_float(record.get("Library_Geolocation__Longitude__s"))
    distance_miles = None
    status = "found_unverified"

    if latitude is not None and longitude is not None and record_latitude is not None and record_longitude is not None:
        distance_miles = haversine_miles(latitude, longitude, record_latitude, record_longitude)
        status = "matched" if distance_miles <= LFL_CHARTER_MATCH_RADIUS_MILES else "location_mismatch"

    summary = summarize_lfl_record(record, distance_miles, status)
    summary["charter_number"] = charter
    return summary


def parse_openai_output(response_payload: dict[str, Any]) -> dict[str, Any]:
    if response_payload.get("output_text"):
        return json.loads(response_payload["output_text"])

    for item in response_payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise RuntimeError(content.get("refusal", "OpenAI refused the request"))
            if isinstance(content.get("parsed"), dict):
                return content["parsed"]
            if content.get("type") == "output_text" and content.get("text"):
                return json.loads(content["text"])

    raise RuntimeError("OpenAI returned no parseable output")


def post_openai(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def call_openai_for_photos(image_inputs: list[dict[str, Any]]) -> dict[str, Any]:
    user_content: list[dict[str, str]] = [{"type": "input_text", "text": ANALYSIS_USER_PROMPT}]
    for index, image_input in enumerate(image_inputs, start=1):
        image_base64 = base64.b64encode(image_input["data"]).decode("utf-8")
        role = image_input.get("role") or "photo"
        user_content.append({"type": "input_text", "text": f"Image {index}: {role}."})
        user_content.append(
            {
                "type": "input_image",
                "image_url": f"data:{image_input['mime_type']};base64,{image_base64}",
                "detail": "high",
            }
        )

    input_message = [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": ANALYSIS_SYSTEM_PROMPT}],
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]

    schema_format = {
        "type": "json_schema",
        "name": "little_library_analysis",
        "strict": True,
        "schema": ANALYSIS_SCHEMA,
    }

    candidate_payloads = [
        {
            "model": DEFAULT_OPENAI_MODEL,
            "input": input_message,
            "text": {"format": schema_format},
        },
        {
            "model": DEFAULT_OPENAI_MODEL,
            "input": input_message,
            "format": schema_format,
        },
        {
            "model": DEFAULT_OPENAI_MODEL,
            "input": input_message,
            "text": {"format": {"type": "json_object"}},
        },
    ]

    last_error: Exception | None = None
    for payload in candidate_payloads:
        try:
            response_payload = post_openai(payload)
            data = parse_openai_output(response_payload)
            return normalize_model_analysis(data)
        except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as error:
            last_error = error
            continue

    raise RuntimeError(str(last_error) if last_error else "OpenAI analysis failed")


def call_openai_for_books(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    return call_openai_for_photos([{"data": image_bytes, "mime_type": mime_type, "role": "books_photo"}])


def normalize_model_analysis(data: dict[str, Any]) -> dict[str, Any]:
    books = []
    for raw_book in data.get("books", []):
        if not isinstance(raw_book, dict):
            continue
        book = sanitize_book(raw_book)
        if not book["title"]:
            continue
        books.append(book)

    return {
        "library_name_suggestion": str(data.get("library_name_suggestion", "") or "").strip(),
        "library_description": str(data.get("library_description", "") or "").strip(),
        "photo_summary": str(data.get("photo_summary", "") or "").strip(),
        "place_clues": [str(item).strip() for item in data.get("place_clues", []) if str(item).strip()],
        "charter_number": normalize_charter_number(data.get("charter_number"))
        or extract_charter_number_from_text(
            data.get("library_name_suggestion"),
            data.get("library_description"),
            data.get("photo_summary"),
            " ".join(str(item) for item in data.get("place_clues", [])),
        ),
        "books": books,
    }


def build_analysis_response(
    filename: str,
    books_photo_urls: list[str],
    location_photo_urls: list[str],
    photo_urls: list[str],
    location_photo_url: str | None,
    location: GeoPoint | None,
    model_output: dict[str, Any] | None,
    charter_registration: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    output = model_output or {
        "library_name_suggestion": "",
        "library_description": "",
        "photo_summary": "",
        "place_clues": [],
        "charter_number": "",
        "books": [],
    }

    geolocation = (
        location.to_dict()
        if location
        else {
            "latitude": None,
            "longitude": None,
            "source": "unavailable",
            "confidence": 0.0,
            "accuracy_meters": None,
        }
    )

    library_name = output["library_name_suggestion"] or f"Sidewalk Library {datetime.now().strftime('%b %d')}"
    books_photo_url = books_photo_urls[0] if books_photo_urls else ""
    primary_photo_url = location_photo_url or books_photo_url or (photo_urls[0] if photo_urls else "")

    return {
        "photo_filename": filename,
        "photo_url": primary_photo_url,
        "books_photo_url": books_photo_url,
        "books_photo_urls": books_photo_urls,
        "location_photo_url": location_photo_url,
        "location_photo_urls": location_photo_urls,
        "photo_urls": photo_urls,
        "library_name": library_name,
        "library_description": output["library_description"],
        "photo_summary": output["photo_summary"],
        "place_clues": output["place_clues"],
        "charter_number": output.get("charter_number", ""),
        "charter_registration": charter_registration or {},
        "geolocation": geolocation,
        "books": output["books"],
        "warnings": warnings,
    }


def to_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def first_photo_path(*values: Any) -> str:
    for value in values:
        paths = normalize_photo_paths(value)
        if paths:
            return paths[0]
    return ""


def find_existing_library_id(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    charter_number: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> int | None:
    library_id = to_int(payload.get("library_id"))
    if library_id:
        row = connection.execute("SELECT id FROM libraries WHERE id = ?", (library_id,)).fetchone()
        if row:
            return int(row["id"])

    if charter_number:
        row = connection.execute(
            """
            SELECT id
            FROM libraries
            WHERE charter_number = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (charter_number,),
        ).fetchone()
        if row:
            return int(row["id"])

    if latitude is not None and longitude is not None and not to_bool(payload.get("allow_create_duplicate")):
        rows = connection.execute(
            """
            SELECT id, latitude, longitude
            FROM libraries
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
            """
        ).fetchall()
        nearest_id: int | None = None
        nearest_distance: float | None = None
        for row in rows:
            distance_miles = haversine_miles(latitude, longitude, row["latitude"], row["longitude"])
            if nearest_distance is None or distance_miles < nearest_distance:
                nearest_id = int(row["id"])
                nearest_distance = distance_miles
        if nearest_id is not None and nearest_distance is not None and nearest_distance <= 0.05:
            return nearest_id

    return None


def record_library_photos(connection: sqlite3.Connection, library_id: int, payload: dict[str, Any]) -> None:
    photo_rows: list[dict[str, Any]] = []

    def add_photo(role: str, photo_path: Any, metadata: dict[str, Any] | None = None) -> None:
        path = str(photo_path or "").strip().lstrip("/")
        if not path:
            return
        metadata = metadata or {}
        location = metadata.get("location") or {}
        if isinstance(location, GeoPoint):
            latitude = location.latitude
            longitude = location.longitude
            source = location.source
        else:
            latitude = to_float(location.get("latitude")) if isinstance(location, dict) else None
            longitude = to_float(location.get("longitude")) if isinstance(location, dict) else None
            source = str(location.get("source") or "") if isinstance(location, dict) else ""
        photo_rows.append(
            {
                "role": role,
                "photo_path": path,
                "original_filename": metadata.get("original_filename") or metadata.get("filename") or "",
                "content_type": metadata.get("content_type") or "",
                "latitude": latitude,
                "longitude": longitude,
                "location_source": source,
            }
        )

    for record in payload.get("photo_records") or []:
        if isinstance(record, dict):
            add_photo(str(record.get("role") or "photo"), record.get("photo_path"), record)

    for path in normalize_photo_paths(payload.get("books_photo_paths")):
        add_photo("books_photo", path)
    add_photo("books_photo", payload.get("books_photo_path"))

    for path in normalize_photo_paths(payload.get("location_photo_paths")):
        add_photo("location_photo", path)
    add_photo("location_photo", payload.get("location_photo_path"))

    for path in normalize_photo_paths(payload.get("additional_photo_paths")):
        add_photo("supplemental_photo", path)
    for path in normalize_photo_paths(payload.get("photo_paths")):
        add_photo("photo", path)
    add_photo("photo", payload.get("photo_path"))

    seen_paths: set[str] = set()
    for row in photo_rows:
        if row["photo_path"] in seen_paths:
            continue
        seen_paths.add(row["photo_path"])
        connection.execute(
            """
            INSERT OR IGNORE INTO library_photos (
                library_id,
                role,
                photo_path,
                original_filename,
                content_type,
                latitude,
                longitude,
                location_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                library_id,
                row["role"],
                row["photo_path"],
                row["original_filename"],
                row["content_type"],
                row["latitude"],
                row["longitude"],
                row["location_source"],
            ),
        )


def upsert_library_inventory(
    connection: sqlite3.Connection,
    library_id: int,
    sanitized_books: list[dict[str, Any]],
    replace_inventory: bool,
) -> None:
    seen_identities: set[str] = set()
    now = current_timestamp()
    existing_rows = connection.execute(
        """
        SELECT *
        FROM books
        WHERE library_id = ?
          AND COALESCE(status, 'active') = 'active'
        """,
        (library_id,),
    ).fetchall()
    existing_by_identity = {book_identity(row): row for row in existing_rows}

    for book in sanitized_books:
        identity = book_identity(book)
        if not identity or identity in seen_identities:
            continue
        seen_identities.add(identity)
        search_blob = build_search_blob(
            book["title"],
            book["author"],
            book["isbn"],
            book["publisher"],
            book["genre"],
            book["notes"],
        )
        existing = existing_by_identity.get(identity)
        if existing:
            connection.execute(
                """
                UPDATE books
                SET title = ?,
                    author = ?,
                    isbn = ?,
                    publisher = ?,
                    published_year = ?,
                    genre = ?,
                    format = ?,
                    condition = ?,
                    confidence = ?,
                    notes = ?,
                    search_blob = ?,
                    status = 'active',
                    last_seen_at = ?,
                    removed_at = NULL
                WHERE id = ?
                """,
                (
                    book["title"],
                    book["author"],
                    book["isbn"],
                    book["publisher"],
                    book["published_year"],
                    book["genre"],
                    book["format"],
                    book["condition"],
                    book["confidence"],
                    book["notes"],
                    search_blob,
                    now,
                    existing["id"],
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO books (
                    library_id,
                    title,
                    author,
                    isbn,
                    publisher,
                    published_year,
                    genre,
                    format,
                    condition,
                    confidence,
                    notes,
                    status,
                    first_seen_at,
                    last_seen_at,
                    search_blob
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    library_id,
                    book["title"],
                    book["author"],
                    book["isbn"],
                    book["publisher"],
                    book["published_year"],
                    book["genre"],
                    book["format"],
                    book["condition"],
                    book["confidence"],
                    book["notes"],
                    now,
                    now,
                    search_blob,
                ),
            )

    if replace_inventory:
        for row in existing_rows:
            if book_identity(row) in seen_identities:
                continue
            connection.execute(
                """
                UPDATE books
                SET status = 'removed',
                    removed_at = ?,
                    last_seen_at = ?
                WHERE id = ?
                """,
                (now, now, row["id"]),
            )


def insert_library(payload: dict[str, Any]) -> int:
    library_name = str(payload.get("library_name") or "").strip()
    description = str(payload.get("library_description") or "").strip()
    books_photo_path = first_photo_path(payload.get("books_photo_path"), payload.get("books_photo_paths"))
    location_photo_path = first_photo_path(payload.get("location_photo_path"), payload.get("location_photo_paths"))
    legacy_photo_path = first_photo_path(payload.get("photo_path"), payload.get("photo_paths"))
    photo_path = location_photo_path or books_photo_path or legacy_photo_path
    icon_source_photo_path = select_icon_source_photo(payload, photo_path)
    raw_place_clues = payload.get("place_clues", [])
    if isinstance(raw_place_clues, str):
        place_clues_list = [item.strip() for item in raw_place_clues.split(",") if item.strip()]
    elif isinstance(raw_place_clues, list):
        place_clues_list = [str(item).strip() for item in raw_place_clues if str(item).strip()]
    else:
        place_clues_list = []
    place_clues = json.dumps(place_clues_list)

    geo = payload.get("geolocation") or {}
    latitude = to_float(geo.get("latitude"))
    longitude = to_float(geo.get("longitude"))
    source = str(geo.get("source") or "manual").strip() or "manual"
    confidence = clamp_confidence(geo.get("confidence"))
    accuracy_meters = to_float(geo.get("accuracy_meters"))

    books = payload.get("books") or []
    sanitized_books = [sanitize_book(book) for book in books if isinstance(book, dict)]
    sanitized_books = [book for book in sanitized_books if book["title"]]
    charter_number = normalize_charter_number(payload.get("charter_number")) or extract_charter_number_from_text(
        library_name,
        description,
        payload.get("photo_summary"),
        " ".join(place_clues_list),
    )
    charter_registration = parse_json_object(payload.get("charter_registration"))
    if charter_number and not charter_registration:
        charter_registration = lookup_lfl_registration(charter_number, latitude, longitude)
    elif charter_number and charter_registration:
        charter_registration.setdefault("charter_number", charter_number)
    charter_lookup_status = str(charter_registration.get("status") or "").strip() if charter_registration else ""
    charter_record_checked_at = str(charter_registration.get("checked_at") or "").strip() if charter_registration else ""
    charter_record_distance_miles = to_float(charter_registration.get("distance_miles")) if charter_registration else None
    charter_record_json = json.dumps(charter_registration, sort_keys=True) if charter_registration else ""

    with get_connection() as connection:
        library_id = find_existing_library_id(connection, payload, charter_number, latitude, longitude)
        require_new_library_location(latitude, longitude)
        if not library_id:
            require_new_library_name(library_name)
        replace_inventory_provided = "replace_inventory" in payload
        replace_inventory = to_bool(payload.get("replace_inventory"))
        if library_id and not replace_inventory_provided:
            replace_inventory = True

        if library_id:
            connection.execute(
                """
                UPDATE libraries
                SET name = COALESCE(NULLIF(?, ''), name),
                    description = COALESCE(NULLIF(?, ''), description),
                    latitude = COALESCE(?, latitude),
                    longitude = COALESCE(?, longitude),
                    location_source = COALESCE(NULLIF(?, ''), location_source),
                    location_confidence = COALESCE(?, location_confidence),
                    browser_accuracy_meters = COALESCE(?, browser_accuracy_meters),
                    photo_path = COALESCE(NULLIF(?, ''), photo_path),
                    books_photo_path = COALESCE(NULLIF(?, ''), books_photo_path),
                    location_photo_path = COALESCE(NULLIF(?, ''), location_photo_path),
                    icon_path = COALESCE(NULLIF(?, ''), icon_path),
                    charter_number = COALESCE(NULLIF(?, ''), charter_number),
                    charter_lookup_status = COALESCE(NULLIF(?, ''), charter_lookup_status),
                    charter_record_checked_at = COALESCE(NULLIF(?, ''), charter_record_checked_at),
                    charter_record_distance_miles = COALESCE(?, charter_record_distance_miles),
                    charter_record_json = COALESCE(NULLIF(?, ''), charter_record_json),
                    place_clues = ?
                WHERE id = ?
                """,
                (
                    library_name,
                    description,
                    latitude,
                    longitude,
                    source,
                    confidence,
                    accuracy_meters,
                    photo_path,
                    books_photo_path,
                    location_photo_path,
                    payload.get("icon_path") or "",
                    charter_number,
                    charter_lookup_status,
                    charter_record_checked_at,
                    charter_record_distance_miles,
                    charter_record_json,
                    place_clues,
                    library_id,
                ),
            )
        else:
            cursor = connection.execute(
                """
                INSERT INTO libraries (
                    name,
                    description,
                    latitude,
                    longitude,
                    location_source,
                    location_confidence,
                    browser_accuracy_meters,
                    photo_path,
                    books_photo_path,
                    location_photo_path,
                    icon_path,
                    charter_number,
                    charter_lookup_status,
                    charter_record_checked_at,
                    charter_record_distance_miles,
                    charter_record_json,
                    place_clues
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    library_name,
                    description,
                    latitude,
                    longitude,
                    source,
                    confidence,
                    accuracy_meters,
                    photo_path,
                    books_photo_path,
                    location_photo_path,
                    str(payload.get("icon_path") or ""),
                    charter_number,
                    charter_lookup_status,
                    charter_record_checked_at,
                    charter_record_distance_miles,
                    charter_record_json,
                    place_clues,
                ),
            )
            library_id = int(cursor.lastrowid)

        record_library_photos(connection, library_id, payload)
        icon_path = create_library_icon(library_id, library_name, icon_source_photo_path)
        if icon_path:
            connection.execute("UPDATE libraries SET icon_path = ? WHERE id = ?", (icon_path, library_id))
        upsert_library_inventory(connection, library_id, sanitized_books, replace_inventory)

    refresh_library_map()
    refresh_pages_data()
    return library_id


def get_counts() -> dict[str, int]:
    with get_connection() as connection:
        library_count = connection.execute("SELECT COUNT(*) FROM libraries").fetchone()[0]
        book_count = connection.execute(
            "SELECT COUNT(*) FROM books WHERE COALESCE(status, 'active') = 'active'"
        ).fetchone()[0]

    return {"libraries": int(library_count), "books": int(book_count)}


def category_matches(row: sqlite3.Row, category: str) -> bool:
    normalized_category = normalize_text(category).replace(" ", "-")
    if not normalized_category:
        return True

    text = build_search_blob(
        row["title"],
        row["author"],
        row["publisher"],
        row["genre"],
        row["format"],
        row["notes"],
    )

    if normalized_category in {"non-fiction", "nonfiction"}:
        has_nonfiction_signal = any(marker in text for marker in NONFICTION_MARKERS)
        has_fiction_signal = any(marker in normalize_text(row["genre"]) for marker in FICTION_MARKERS)
        return has_nonfiction_signal and not has_fiction_signal

    markers = CATEGORY_MARKERS.get(normalized_category)
    if not markers:
        return True
    return any(marker in text for marker in markers)


def search_books(
    query: str,
    latitude: float | None,
    longitude: float | None,
    radius_miles: float,
    category: str = "",
    limit: int = 30,
) -> list[dict[str, Any]]:
    normalized_query = normalize_text(query)
    terms = [term for term in normalized_query.split(" ") if term]
    if not terms and not normalize_text(category):
        return []

    sql = """
        SELECT
            b.id AS book_id,
            b.title,
            b.author,
            b.isbn,
            b.publisher,
            b.published_year,
            b.genre,
            b.format,
            b.condition,
            b.confidence,
            b.notes,
            b.search_blob,
            l.id AS library_id,
            l.name AS library_name,
            l.description AS library_description,
            l.latitude,
            l.longitude,
            l.location_source,
            l.location_confidence,
            l.photo_path,
            l.books_photo_path,
            l.location_photo_path,
            l.icon_path,
            l.charter_number,
            l.charter_record_json
        FROM books b
        JOIN libraries l ON l.id = b.library_id
    """

    where_clauses = ["COALESCE(b.status, 'active') = 'active'"]
    params: list[Any] = []
    for term in terms:
        where_clauses.append("b.search_blob LIKE ?")
        params.append(f"%{term}%")

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY b.confidence DESC, l.location_confidence DESC, b.title ASC"

    results: list[dict[str, Any]] = []
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()

    for row in rows:
        row_lat = row["latitude"]
        row_lon = row["longitude"]
        books_photo_path = row["books_photo_path"] or row["photo_path"]
        location_photo_path = row["location_photo_path"] or row["photo_path"] or row["books_photo_path"]
        distance_miles = None
        if latitude is not None and longitude is not None and row_lat is not None and row_lon is not None:
            distance_miles = haversine_miles(latitude, longitude, row_lat, row_lon)
            if distance_miles > radius_miles:
                continue
        if not category_matches(row, category):
            continue
        official_address = format_official_address(row["charter_record_json"])
        icon_url = public_icon_path(row["icon_path"])

        results.append(
            {
                "book_id": row["book_id"],
                "title": row["title"],
                "author": row["author"],
                "isbn": row["isbn"],
                "publisher": row["publisher"],
                "published_year": row["published_year"],
                "genre": row["genre"],
                "format": row["format"],
                "condition": row["condition"],
                "confidence": row["confidence"],
                "notes": row["notes"],
                "library": {
                    "id": row["library_id"],
                    "csn": f"CSN-{row['library_id']}",
                    "name": row["library_name"],
                    "description": row["library_description"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "marker_latitude": row["latitude"],
                    "marker_longitude": row["longitude"],
                    "marker_location_source": row["location_source"] or "",
                    "location_source": row["location_source"],
                    "location_confidence": row["location_confidence"],
                    "charter_number": row["charter_number"],
                    "official_address": official_address,
                    "location_label": official_address or "",
                    "icon_url": icon_url,
                    "photo_url": public_upload_url(location_photo_path),
                    "books_photo_url": public_upload_url(books_photo_path),
                    "location_photo_url": public_upload_url(location_photo_path),
                },
                "distance_miles": distance_miles,
            }
        )

    results.sort(
        key=lambda item: (
            item["distance_miles"] is None,
            item["distance_miles"] if item["distance_miles"] is not None else 10_000,
            -(item["confidence"] or 0),
            item["title"].lower(),
        )
    )
    return results[:limit]


def list_library_books(library_id: int) -> list[dict[str, Any]]:
    sql = """
        SELECT
            id,
            title,
            author,
            isbn,
            publisher,
            published_year,
            genre,
            format,
            condition,
            confidence,
            notes,
            status
        FROM books
        WHERE library_id = ?
          AND COALESCE(status, 'active') = 'active'
        ORDER BY title ASC, id ASC
    """
    with get_connection() as connection:
        rows = connection.execute(sql, (library_id,)).fetchall()

    return [
        {
            "book_id": row["id"],
            "title": row["title"],
            "author": row["author"],
            "isbn": row["isbn"],
            "publisher": row["publisher"],
            "published_year": row["published_year"],
            "genre": row["genre"],
            "format": row["format"],
            "condition": row["condition"],
            "confidence": row["confidence"],
            "notes": row["notes"],
            "status": row["status"] or "active",
        }
        for row in rows
    ]


def list_libraries() -> list[dict[str, Any]]:
    sql = """
        SELECT
            l.id,
            l.name,
            l.description,
            l.latitude,
            l.longitude,
            l.location_source,
            l.location_confidence,
            l.photo_path,
            l.books_photo_path,
            l.location_photo_path,
            l.icon_path,
            l.charter_number,
            l.charter_lookup_status,
            l.charter_record_checked_at,
            l.charter_record_distance_miles,
            l.charter_record_json,
            l.place_clues,
            COUNT(b.id) AS book_count,
            GROUP_CONCAT(b.title, '||') AS book_titles
        FROM libraries l
        LEFT JOIN books b
            ON b.library_id = l.id
           AND COALESCE(b.status, 'active') = 'active'
        GROUP BY l.id
        ORDER BY l.created_at DESC, l.id DESC
    """
    libraries: list[dict[str, Any]] = []
    with get_connection() as connection:
        rows = connection.execute(sql).fetchall()

    for row in rows:
        books_photo_path = row["books_photo_path"] or row["photo_path"]
        location_photo_path = row["location_photo_path"] or row["photo_path"] or row["books_photo_path"]
        icon_url = public_icon_path(row["icon_path"])
        book_titles = [title for title in (row["book_titles"] or "").split("||") if title]
        official_address = format_official_address(row["charter_record_json"])
        try:
            place_clues = json.loads(row["place_clues"] or "[]")
        except json.JSONDecodeError:
            place_clues = []
        libraries.append(
            {
                "id": row["id"],
                "csn": f"CSN-{row['id']}",
                "name": row["name"],
                "description": row["description"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "marker_latitude": row["latitude"],
                "marker_longitude": row["longitude"],
                "marker_location_source": row["location_source"] or "",
                "location_source": row["location_source"],
                "location_confidence": row["location_confidence"],
                "charter_number": row["charter_number"] or "",
                "charter_lookup_status": row["charter_lookup_status"] or "",
                "charter_record_checked_at": row["charter_record_checked_at"] or "",
                "charter_record_distance_miles": row["charter_record_distance_miles"],
                "official_address": official_address,
                "location_label": official_address or "",
                "icon_url": icon_url,
                "photo_url": public_upload_url(location_photo_path),
                "books_photo_url": public_upload_url(books_photo_path),
                "location_photo_url": public_upload_url(location_photo_path),
                "place_clues": place_clues,
                "book_count": int(row["book_count"] or 0),
                "sample_books": book_titles[:5],
            }
        )

    return libraries


def build_public_openapi_spec() -> dict[str, Any]:
    rate_limit = f"{PUBLIC_API_RATE_LIMIT_REQUESTS} requests per {PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS} seconds per IP"
    library_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "csn": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "marker_latitude": {"type": "number"},
            "marker_longitude": {"type": "number"},
            "marker_location_source": {"type": "string"},
            "official_address": {"type": "string"},
            "charter_number": {"type": "string"},
            "icon_url": {"type": "string"},
            "book_count": {"type": "integer"},
            "distance_miles": {"type": ["number", "null"]},
        },
    }
    book_schema = {
        "type": "object",
        "properties": {
            "book_id": {"type": "integer"},
            "title": {"type": "string"},
            "author": {"type": "string"},
            "isbn": {"type": "string"},
            "publisher": {"type": "string"},
            "published_year": {"type": "string"},
            "genre": {"type": "string"},
            "library": library_schema,
            "distance_miles": {"type": ["number", "null"]},
        },
    }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Civitas Library Public API",
            "version": PUBLIC_API_VERSION,
            "description": (
                "Community-friendly read API for searching neighborhood mini-library books and shelf locations. "
                f"Fair-use rate limit: {rate_limit}."
            ),
            "contact": {"email": "civitaslibrary@gmail.com"},
            "license": {"name": "Apache-2.0"},
        },
        "paths": {
            "/api/v1/search": {
                "get": {
                    "summary": "Search active books",
                    "parameters": [
                        {"name": "q", "in": "query", "schema": {"type": "string"}},
                        {"name": "category", "in": "query", "schema": {"type": "string"}},
                        {"name": "zip", "in": "query", "schema": {"type": "string"}},
                        {"name": "lat", "in": "query", "schema": {"type": "number"}},
                        {"name": "lon", "in": "query", "schema": {"type": "number"}},
                        {"name": "radius_miles", "in": "query", "schema": {"type": "number", "default": DEFAULT_RADIUS_MILES}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": PUBLIC_API_DEFAULT_LIMIT}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Search results",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"results": {"type": "array", "items": book_schema}},
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/v1/libraries": {
                "get": {
                    "summary": "List mini libraries",
                    "parameters": [
                        {"name": "q", "in": "query", "schema": {"type": "string"}},
                        {"name": "zip", "in": "query", "schema": {"type": "string"}},
                        {"name": "lat", "in": "query", "schema": {"type": "number"}},
                        {"name": "lon", "in": "query", "schema": {"type": "number"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": PUBLIC_API_DEFAULT_LIMIT}},
                        {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Libraries",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"libraries": {"type": "array", "items": library_schema}},
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/v1/libraries/{id}": {
                "get": {
                    "summary": "Get one mini library and its active books",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "Library detail"}},
                }
            },
        },
    }


class LibraryAtlasHandler(BaseHTTPRequestHandler):
    server_version = "CivitasLibrary/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.serve_file(STATIC_DIR / "index.html")
            return
        if path == "/styles.css":
            self.serve_file(STATIC_DIR / "styles.css")
            return
        if path == "/app.js":
            self.serve_file(STATIC_DIR / "app.js")
            return
        if path == "/api/config":
            self.send_json(
                {
                    "status": "ok",
                    "counts": get_counts(),
                    "openai_enabled": bool(os.getenv("OPENAI_API_KEY")),
                    "model": DEFAULT_OPENAI_MODEL,
                }
            )
            return
        if path == "/api/libraries":
            libraries = list_libraries()
            self.send_json({"libraries": libraries, "count": len(libraries)})
            return
        if path == "/api/v1/openapi.json":
            self.send_json(build_public_openapi_spec())
            return
        if path == "/api/v1/search":
            headers = self.public_api_rate_limit_headers("search")
            if headers is None:
                return
            self.handle_public_search(parsed, headers)
            return
        if path == "/api/v1/libraries":
            headers = self.public_api_rate_limit_headers("libraries")
            if headers is None:
                return
            self.handle_public_libraries(parsed, headers)
            return
        library_detail_match = re.fullmatch(r"/api/v1/libraries/(\d+)", path)
        if library_detail_match:
            headers = self.public_api_rate_limit_headers("libraries")
            if headers is None:
                return
            self.handle_public_library_detail(int(library_detail_match.group(1)), headers)
            return
        if path.startswith("/data/uploads/"):
            if os.getenv("CIVITAS_SERVE_UPLOADS") != "1":
                self.send_error(HTTPStatus.NOT_FOUND, "Uploaded originals are not publicly served")
                return
            relative = path.lstrip("/")
            target = BASE_DIR / relative
            self.serve_file(target)
            return
        if path.startswith("/library-icons/"):
            target = LIBRARY_ICONS_DIR / Path(path).name
            self.serve_file(target)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/api/analyze-photo":
            self.handle_analyze_photo()
            return
        if parsed.path == "/api/libraries":
            self.handle_save_library()
            return
        if parsed.path in {"/api/mobile/libraries", "/api/contributions"}:
            self.handle_mobile_library_upload()
            return
        if parsed.path == "/api/search":
            self.handle_search()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        mime_type, _ = mimetypes.guess_type(str(path))
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(
        self,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for header, value in (headers or {}).items():
            self.send_header(header, value)
        self.end_headers()
        self.wfile.write(raw)

    def public_api_client_key(self, scope: str) -> str:
        forwarded_for = self.headers.get("X-Forwarded-For", "")
        address = forwarded_for.split(",", 1)[0].strip() if forwarded_for else self.client_address[0]
        return f"{scope}:{address}"

    def public_api_rate_limit_headers(self, scope: str) -> dict[str, str] | None:
        rate_limit = check_public_api_rate_limit(self.public_api_client_key(scope))
        headers = rate_limit_headers(rate_limit)
        if rate_limit["allowed"]:
            return headers

        self.send_json(
            {
                "error": "Rate limit exceeded. Please slow down and cache responses for community-friendly use.",
                "limit": rate_limit["limit"],
                "window_seconds": PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS,
                "retry_after_seconds": rate_limit["retry_after"],
            },
            HTTPStatus.TOO_MANY_REQUESTS,
            headers,
        )
        return None

    def handle_public_search(self, parsed: Any, headers: dict[str, str]) -> None:
        try:
            params = parse_qs(parsed.query)
            query = query_value(params, "q", "query")
            category = query_value(params, "category", "genre")
            if not query and not category:
                self.send_json({"error": "Query parameter 'q' or 'category' is required."}, HTTPStatus.BAD_REQUEST, headers)
                return

            latitude, longitude, location_label = resolve_public_api_location(params)
            radius_miles = bounded_float(
                query_value(params, "radius_miles", "radius"),
                DEFAULT_RADIUS_MILES,
                1.0,
                250.0,
            )
            limit = bounded_int(
                query_value(params, "limit"),
                PUBLIC_API_DEFAULT_LIMIT,
                1,
                PUBLIC_API_MAX_LIMIT,
            )
            results = search_books(query, latitude, longitude, radius_miles, category, limit)
            self.send_json(
                {
                    "api_version": PUBLIC_API_VERSION,
                    "query": {
                        "q": query,
                        "category": category,
                        "latitude": latitude,
                        "longitude": longitude,
                        "location_label": location_label,
                        "radius_miles": radius_miles,
                        "limit": limit,
                    },
                    "count": len(results),
                    "results": results,
                },
                headers=headers,
            )
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST, headers)

    def handle_public_libraries(self, parsed: Any, headers: dict[str, str]) -> None:
        try:
            params = parse_qs(parsed.query)
            limit = bounded_int(query_value(params, "limit"), PUBLIC_API_DEFAULT_LIMIT, 1, PUBLIC_API_MAX_LIMIT)
            offset = bounded_int(query_value(params, "offset"), 0, 0, 1_000_000)
            query = normalize_text(query_value(params, "q", "query"))
            latitude, longitude, location_label = resolve_public_api_location(params)
            libraries = list_libraries()

            if query:
                libraries = [
                    library
                    for library in libraries
                    if query
                    in build_search_blob(
                        library.get("name"),
                        library.get("description"),
                        library.get("charter_number"),
                        " ".join(library.get("sample_books") or []),
                    )
                ]

            enriched_libraries: list[dict[str, Any]] = []
            for library in libraries:
                item = dict(library)
                distance_miles = None
                if latitude is not None and longitude is not None and item.get("latitude") is not None and item.get("longitude") is not None:
                    distance_miles = haversine_miles(latitude, longitude, item["latitude"], item["longitude"])
                item["distance_miles"] = distance_miles
                enriched_libraries.append(item)

            if latitude is not None and longitude is not None:
                enriched_libraries.sort(
                    key=lambda item: (
                        item["distance_miles"] is None,
                        item["distance_miles"] if item["distance_miles"] is not None else 10_000,
                        item["id"],
                    )
                )

            page = enriched_libraries[offset : offset + limit]
            self.send_json(
                {
                    "api_version": PUBLIC_API_VERSION,
                    "query": {
                        "q": query,
                        "latitude": latitude,
                        "longitude": longitude,
                        "location_label": location_label,
                        "limit": limit,
                        "offset": offset,
                    },
                    "count": len(page),
                    "total": len(enriched_libraries),
                    "libraries": page,
                },
                headers=headers,
            )
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST, headers)

    def handle_public_library_detail(self, library_id: int, headers: dict[str, str]) -> None:
        libraries = list_libraries()
        library = next((item for item in libraries if int(item["id"]) == library_id), None)
        if not library:
            self.send_json({"error": f"Library {library_id} was not found."}, HTTPStatus.NOT_FOUND, headers)
            return

        self.send_json(
            {
                "api_version": PUBLIC_API_VERSION,
                "library": library,
                "books": list_library_books(library_id),
            },
            headers=headers,
        )

    def handle_analyze_photo(self) -> None:
        try:
            fields, files = parse_multipart_form_data(self)
            books_uploads = file_list(files, "books_photo", "books_photo[]")
            location_uploads = file_list(files, "location_photo", "location_photo[]", "photo")
            supplemental_uploads = file_list(files, "additional_photo", "additional_photos", "photos", "photos[]")
            if not books_uploads and not location_uploads and not supplemental_uploads:
                self.send_json({"error": "Upload at least one photo for this library."}, HTTPStatus.BAD_REQUEST)
                return

            saved_books = save_uploaded_images(books_uploads, "books_photo")
            saved_locations = save_uploaded_images(location_uploads, "location_photo")
            saved_supplemental = save_uploaded_images(supplemental_uploads, "supplemental_photo")
            all_saved = saved_books + saved_locations + saved_supplemental
            gps_photo = require_uploaded_photo_gps(all_saved)

            browser_location = build_browser_location(fields)
            photo_locations = [item["location"] for item in saved_locations + saved_books + saved_supplemental if item["location"]]
            location = choose_best_location(*photo_locations, browser_location)

            warnings: list[str] = []
            if not saved_books:
                warnings.append(
                    "No close-up books photo was attached. This library can still be saved, but book rows may need manual entry."
                )

            model_output: dict[str, Any] | None = None
            try:
                analysis_photos = saved_books or all_saved
                image_inputs = [
                    {
                        "data": item["data"],
                        "mime_type": item["content_type"] or "image/jpeg",
                        "role": item["role"],
                    }
                    for item in analysis_photos
                ]
                model_output = call_openai_for_photos(image_inputs)
            except RuntimeError as error:
                warnings.append(
                    f"Automated book extraction is unavailable right now: {error}. You can still add or correct books manually before saving."
                )

            charter_number = normalize_charter_number((model_output or {}).get("charter_number"))
            charter_registration = lookup_lfl_registration(
                charter_number,
                location.latitude if location else None,
                location.longitude if location else None,
            ) if charter_number else {}
            if charter_registration.get("status") == "location_mismatch":
                warnings.append(
                    "The visible Little Free Library charter number was found in the public registry, but its public location does not match this upload closely."
                )

            filename = ", ".join(item["original_filename"] for item in all_saved[:3])
            if len(all_saved) > 3:
                filename += f" +{len(all_saved) - 3} more"
            books_photo_urls = [item["photo_url"] for item in saved_books]
            location_photo_urls = [item["photo_url"] for item in saved_locations]
            photo_urls = [item["photo_url"] for item in all_saved]
            response_payload = build_analysis_response(
                filename,
                books_photo_urls,
                location_photo_urls,
                photo_urls,
                location_photo_urls[0] if location_photo_urls else None,
                location,
                model_output,
                charter_registration,
                warnings,
            )
            response_payload["books_photo_paths"] = [item["photo_path"] for item in saved_books]
            response_payload["location_photo_paths"] = [item["photo_path"] for item in saved_locations]
            response_payload["additional_photo_paths"] = [item["photo_path"] for item in saved_supplemental]
            response_payload["photo_paths"] = [item["photo_path"] for item in all_saved]
            response_payload["icon_source_photo_path"] = gps_photo["photo_path"]
            self.send_json(response_payload)
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - defensive server guard
            self.send_json({"error": f"Unexpected server error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_mobile_library_upload(self) -> None:
        try:
            fields, files = parse_multipart_form_data(self)
            payload_text = fields.get("payload")
            if not payload_text:
                self.send_json({"error": "A JSON payload field is required."}, HTTPStatus.BAD_REQUEST)
                return

            payload = json.loads(payload_text)
            if not isinstance(payload, dict):
                self.send_json({"error": "Payload must be a JSON object."}, HTTPStatus.BAD_REQUEST)
                return

            books_uploads = file_list(files, "books_photo", "books_photo[]")
            location_uploads = file_list(files, "location_photo", "location_photo[]", "photo")
            supplemental_uploads = file_list(files, "additional_photo", "additional_photos", "photos", "photos[]")
            saved_books = save_uploaded_images(books_uploads, "books_photo")
            saved_locations = save_uploaded_images(location_uploads, "location_photo")
            saved_supplemental = save_uploaded_images(supplemental_uploads, "supplemental_photo")
            all_saved = saved_books + saved_locations + saved_supplemental
            if not all_saved:
                self.send_json({"error": "Upload at least one GPS-tagged photo for this library."}, HTTPStatus.BAD_REQUEST)
                return
            gps_photo = require_uploaded_photo_gps(all_saved)
            payload["geolocation"] = gps_photo["location"].to_dict()
            payload["icon_source_photo_path"] = gps_photo["photo_path"]

            if saved_books:
                payload["books_photo_paths"] = [item["photo_path"] for item in saved_books]
                payload["books_photo_path"] = saved_books[0]["photo_path"]
            if saved_locations:
                payload["location_photo_paths"] = [item["photo_path"] for item in saved_locations]
                payload["location_photo_path"] = saved_locations[0]["photo_path"]
            if saved_supplemental:
                payload["additional_photo_paths"] = [item["photo_path"] for item in saved_supplemental]
            if all_saved:
                payload["photo_paths"] = [item["photo_path"] for item in all_saved]
                payload["photo_records"] = photo_records_from_saved(all_saved)

            # Do not store device-local paths such as content:// URIs in the central database.
            for key in ("photo_path", "books_photo_path", "location_photo_path"):
                photo_path = str(payload.get(key) or "")
                if photo_path and not photo_path.startswith("data/uploads/"):
                    payload[key] = ""
            for key in ("photo_paths", "books_photo_paths", "location_photo_paths", "additional_photo_paths"):
                payload[key] = [path for path in normalize_photo_paths(payload.get(key)) if path.startswith("data/uploads/")]
            payload["photo_path"] = payload.get("location_photo_path") or payload.get("books_photo_path") or payload.get("photo_path") or ""

            library_id = insert_library(payload)
            with get_connection() as connection:
                ingestion_run_id = create_ingestion_run(
                    connection,
                    source="mobile",
                    status="accepted",
                    notes="Accepted mobile library contribution.",
                )
                record_photo_evidence(
                    connection,
                    ingestion_run_id=ingestion_run_id,
                    library_id=library_id,
                    photos=all_saved,
                    accepted=True,
                )
                complete_ingestion_run(connection, ingestion_run_id, "accepted")
            books_photo_urls = [item["photo_url"] for item in saved_books]
            location_photo_urls = [item["photo_url"] for item in saved_locations]
            self.send_json(
                {
                    "status": "saved",
                    "library_id": library_id,
                    "photo_url": (location_photo_urls or books_photo_urls or [None])[0],
                    "books_photo_url": books_photo_urls[0] if books_photo_urls else None,
                    "books_photo_urls": books_photo_urls,
                    "location_photo_url": location_photo_urls[0] if location_photo_urls else None,
                    "location_photo_urls": location_photo_urls,
                    "counts": get_counts(),
                },
                HTTPStatus.CREATED,
            )
        except json.JSONDecodeError:
            self.send_json({"error": "Payload must be valid JSON."}, HTTPStatus.BAD_REQUEST)
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - defensive server guard
            self.send_json({"error": f"Unexpected server error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_save_library(self) -> None:
        try:
            payload = parse_json_body(self)
            library_id = insert_library(payload)
            self.send_json(
                {
                    "status": "saved",
                    "library_id": library_id,
                    "counts": get_counts(),
                },
                HTTPStatus.CREATED,
            )
        except json.JSONDecodeError:
            self.send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - defensive server guard
            self.send_json({"error": f"Unexpected server error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_search(self) -> None:
        try:
            payload = parse_json_body(self)
            query = str(payload.get("query") or "").strip()
            category = str(payload.get("category") or "").strip()
            latitude = to_float(payload.get("latitude"))
            longitude = to_float(payload.get("longitude"))
            radius_miles = to_float(payload.get("radius_miles")) or DEFAULT_RADIUS_MILES

            if not query and not category:
                self.send_json({"error": "Search query or category is required."}, HTTPStatus.BAD_REQUEST)
                return

            results = search_books(query, latitude, longitude, radius_miles, category)
            self.send_json({"results": results, "count": len(results)})
        except json.JSONDecodeError:
            self.send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - defensive server guard
            self.send_json({"error": f"Unexpected server error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def run_server() -> None:
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), LibraryAtlasHandler)
    print(f"Civitas Library running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
