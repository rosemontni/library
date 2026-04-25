from __future__ import annotations

import base64
import json
import math
import mimetypes
import os
import re
import sqlite3
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
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "little_library_atlas.db"

HOST = "127.0.0.1"
PORT = 8000
DEFAULT_RADIUS_MILES = 25.0
MAX_IMAGE_BYTES = 25 * 1024 * 1024

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
        "books",
    ],
    "properties": {
        "library_name_suggestion": {"type": "string"},
        "library_description": {"type": "string"},
        "photo_summary": {"type": "string"},
        "place_clues": {"type": "array", "items": {"type": "string"}},
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

ANALYSIS_USER_PROMPT = """Analyze this photo of a little library.

Return JSON with:
- library_name_suggestion: a short descriptive nickname for this library
- library_description: one or two sentences describing the library setup and condition
- photo_summary: a plain-language summary of what is in the image
- place_clues: visible clues such as street signs, murals, house numbers, nearby businesses, or neighborhood hints
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


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


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
                search_blob TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_books_library_id ON books(library_id);
            CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
            CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
            CREATE INDEX IF NOT EXISTS idx_libraries_coords ON libraries(latitude, longitude);
            """
        )


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


def clamp_confidence(value: Any) -> float:
    numeric = to_float(value)
    if numeric is None:
        return 0.0
    return max(0.0, min(1.0, numeric))


def sanitize_book(raw_book: dict[str, Any]) -> dict[str, Any]:
    book: dict[str, Any] = {}
    for field in BOOK_FIELDS:
        if field == "confidence":
            book[field] = clamp_confidence(raw_book.get(field))
        else:
            book[field] = str(raw_book.get(field, "") or "").strip()
    return book


def unique_upload_path(filename: str | None) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = Path(filename or "capture.jpg").suffix.lower() or ".jpg"
    safe_suffix = suffix if len(suffix) <= 8 else ".jpg"
    return UPLOADS_DIR / f"{timestamp}-{uuid.uuid4().hex}{safe_suffix}"


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8"))


def parse_multipart_form_data(handler: BaseHTTPRequestHandler) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("Expected multipart/form-data")

    content_length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(content_length)
    if len(body) > MAX_IMAGE_BYTES + (2 * 1024 * 1024):
        raise ValueError("Upload is too large")

    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(header + body)

    fields: dict[str, str] = {}
    files: dict[str, dict[str, Any]] = {}

    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue

        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = {
                "filename": filename,
                "content_type": part.get_content_type(),
                "data": payload,
            }
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


def choose_best_location(exif_location: GeoPoint | None, browser_location: GeoPoint | None) -> GeoPoint | None:
    if exif_location:
        return exif_location
    if browser_location:
        return browser_location
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


def call_openai_for_books(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    input_message = [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": ANALYSIS_SYSTEM_PROMPT}],
        },
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": ANALYSIS_USER_PROMPT},
                {
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{image_base64}",
                    "detail": "high",
                },
            ],
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
        "books": books,
    }


def build_analysis_response(
    filename: str,
    photo_url: str,
    location: GeoPoint | None,
    model_output: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    output = model_output or {
        "library_name_suggestion": "",
        "library_description": "",
        "photo_summary": "",
        "place_clues": [],
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

    return {
        "photo_filename": filename,
        "photo_url": photo_url,
        "library_name": library_name,
        "library_description": output["library_description"],
        "photo_summary": output["photo_summary"],
        "place_clues": output["place_clues"],
        "geolocation": geolocation,
        "books": output["books"],
        "warnings": warnings,
    }


def insert_library(payload: dict[str, Any]) -> int:
    library_name = str(payload.get("library_name") or "").strip() or f"Sidewalk Library {datetime.now().strftime('%b %d')}"
    description = str(payload.get("library_description") or "").strip()
    photo_path = str(payload.get("photo_path") or "").strip()
    place_clues = json.dumps(payload.get("place_clues", []))

    geo = payload.get("geolocation") or {}
    latitude = to_float(geo.get("latitude"))
    longitude = to_float(geo.get("longitude"))
    source = str(geo.get("source") or "manual").strip() or "manual"
    confidence = clamp_confidence(geo.get("confidence"))
    accuracy_meters = to_float(geo.get("accuracy_meters"))

    books = payload.get("books") or []
    sanitized_books = [sanitize_book(book) for book in books if isinstance(book, dict)]
    sanitized_books = [book for book in sanitized_books if book["title"]]

    if not sanitized_books:
        raise ValueError("At least one book is required before saving")

    with get_connection() as connection:
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
                place_clues
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                place_clues,
            ),
        )
        library_id = int(cursor.lastrowid)

        for book in sanitized_books:
            search_blob = build_search_blob(
                book["title"],
                book["author"],
                book["isbn"],
                book["publisher"],
                book["genre"],
                book["notes"],
            )
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
                    search_blob
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    search_blob,
                ),
            )

    return library_id


def get_counts() -> dict[str, int]:
    with get_connection() as connection:
        library_count = connection.execute("SELECT COUNT(*) FROM libraries").fetchone()[0]
        book_count = connection.execute("SELECT COUNT(*) FROM books").fetchone()[0]

    return {"libraries": int(library_count), "books": int(book_count)}


def search_books(query: str, latitude: float | None, longitude: float | None, radius_miles: float) -> list[dict[str, Any]]:
    normalized_query = normalize_text(query)
    terms = [term for term in normalized_query.split(" ") if term]
    if not terms:
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
            l.id AS library_id,
            l.name AS library_name,
            l.description AS library_description,
            l.latitude,
            l.longitude,
            l.location_source,
            l.location_confidence,
            l.photo_path
        FROM books b
        JOIN libraries l ON l.id = b.library_id
    """

    where_clauses = []
    params: list[Any] = []
    for term in terms:
        where_clauses.append("b.search_blob LIKE ?")
        params.append(f"%{term}%")

    sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY b.confidence DESC, l.location_confidence DESC, b.title ASC"

    results: list[dict[str, Any]] = []
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()

    for row in rows:
        row_lat = row["latitude"]
        row_lon = row["longitude"]
        distance_miles = None
        if latitude is not None and longitude is not None and row_lat is not None and row_lon is not None:
            distance_miles = haversine_miles(latitude, longitude, row_lat, row_lon)
            if distance_miles > radius_miles:
                continue

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
                    "name": row["library_name"],
                    "description": row["library_description"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "location_source": row["location_source"],
                    "location_confidence": row["location_confidence"],
                    "photo_url": f"/{row['photo_path'].replace(os.sep, '/')}" if row["photo_path"] else None,
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
    return results[:30]


class LibraryAtlasHandler(BaseHTTPRequestHandler):
    server_version = "LittleLibraryAtlas/0.1"

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
        if path.startswith("/data/uploads/"):
            relative = path.lstrip("/")
            target = BASE_DIR / relative
            self.serve_file(target)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/api/analyze-photo":
            self.handle_analyze_photo()
            return
        if parsed.path == "/api/libraries":
            self.handle_save_library()
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

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def handle_analyze_photo(self) -> None:
        try:
            fields, files = parse_multipart_form_data(self)
            upload = files.get("photo")
            if not upload:
                self.send_json({"error": "A photo file is required."}, HTTPStatus.BAD_REQUEST)
                return

            image_bytes = upload["data"]
            if not image_bytes:
                self.send_json({"error": "The uploaded photo is empty."}, HTTPStatus.BAD_REQUEST)
                return
            if len(image_bytes) > MAX_IMAGE_BYTES:
                self.send_json({"error": "Please upload an image smaller than 25 MB."}, HTTPStatus.BAD_REQUEST)
                return

            upload_path = unique_upload_path(upload.get("filename"))
            upload_path.write_bytes(image_bytes)

            photo_path = upload_path.relative_to(BASE_DIR).as_posix()
            photo_url = f"/{photo_path}"
            mime_type = upload.get("content_type") or mimetypes.guess_type(upload_path.name)[0] or "image/jpeg"

            browser_location = build_browser_location(fields)
            exif_location = extract_exif_gps(image_bytes)
            location = choose_best_location(exif_location, browser_location)

            warnings: list[str] = []
            if not exif_location and not browser_location:
                warnings.append(
                    "No photo EXIF GPS or browser geolocation was available, so the location fields still need manual confirmation."
                )

            model_output: dict[str, Any] | None = None
            try:
                model_output = call_openai_for_books(image_bytes, mime_type)
            except RuntimeError as error:
                warnings.append(
                    f"Automated book extraction is unavailable right now: {error}. You can still add or correct books manually before saving."
                )

            response_payload = build_analysis_response(upload_path.name, photo_url, location, model_output, warnings)
            self.send_json(response_payload)
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
            latitude = to_float(payload.get("latitude"))
            longitude = to_float(payload.get("longitude"))
            radius_miles = to_float(payload.get("radius_miles")) or DEFAULT_RADIUS_MILES

            if not query:
                self.send_json({"error": "Search query is required."}, HTTPStatus.BAD_REQUEST)
                return

            results = search_books(query, latitude, longitude, radius_miles)
            self.send_json({"results": results, "count": len(results)})
        except json.JSONDecodeError:
            self.send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - defensive server guard
            self.send_json({"error": f"Unexpected server error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def run_server() -> None:
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), LibraryAtlasHandler)
    print(f"Little Library Atlas running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
