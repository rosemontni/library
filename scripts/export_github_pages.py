from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "little_library_atlas.db"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "docs" / "atlas-data.json"
DEFAULT_ICON_DIR = Path(os.getenv("LIBRARY_ICONS_DIR", str(ROOT_DIR / "docs" / "library-icons")))
ICON_SIZE = 144
DEFAULT_BOX_TYPE = "library"
BOX_TYPE_LABELS = {
    "library": "Little Library",
    "art_gallery": "Little Art Gallery",
}


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_export_schema(connection: sqlite3.Connection) -> None:
    ensure_column(connection, "books", "status", "TEXT NOT NULL DEFAULT 'active'")
    ensure_column(connection, "libraries", "box_type", "TEXT NOT NULL DEFAULT 'library'")
    ensure_column(connection, "libraries", "icon_path", "TEXT")
    ensure_column(connection, "libraries", "charter_number", "TEXT")
    ensure_column(connection, "libraries", "charter_lookup_status", "TEXT")
    ensure_column(connection, "libraries", "charter_record_checked_at", "TEXT")
    ensure_column(connection, "libraries", "charter_record_distance_miles", "REAL")
    ensure_column(connection, "libraries", "charter_record_json", "TEXT")


def parse_place_clues(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()] if isinstance(parsed, list) else []


def format_official_address(raw_value: str | None) -> str:
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


def parse_json_object(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalize_box_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in BOX_TYPE_LABELS else DEFAULT_BOX_TYPE


def box_type_label(value: Any) -> str:
    return BOX_TYPE_LABELS.get(normalize_box_type(value), BOX_TYPE_LABELS[DEFAULT_BOX_TYPE])


def slugify_filename(value: str, fallback: str = "library") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48].strip("-") or fallback


def icon_filename(library_id: int, library_name: str) -> str:
    return f"csn-{library_id:04d}-{slugify_filename(library_name)}.png"


def safe_source_photo_path(raw_path: str | None) -> Path | None:
    normalized = str(raw_path or "").strip().lstrip("/").replace("\\", "/")
    if not normalized:
        return None
    candidate = (ROOT_DIR / normalized).resolve()
    try:
        candidate.relative_to(ROOT_DIR.resolve())
    except ValueError:
        return None
    return candidate


def create_library_icon(library_id: int, library_name: str, source_photo_path: str | None) -> str:
    source = safe_source_photo_path(source_photo_path)
    if not source or not source.exists():
        return ""

    DEFAULT_ICON_DIR.mkdir(parents=True, exist_ok=True)
    output = DEFAULT_ICON_DIR / icon_filename(library_id, library_name)
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            resample = getattr(Image, "Resampling", Image).LANCZOS
            icon = ImageOps.fit(image, (ICON_SIZE, ICON_SIZE), method=resample)
            icon.save(output, format="PNG", optimize=True)
    except (OSError, UnidentifiedImageError):
        return ""
    return f"library-icons/{output.name}"


def ensure_library_icon(row: sqlite3.Row) -> str:
    existing_icon_path = str(row["icon_path"] or "").strip().replace("\\", "/")
    if existing_icon_path:
        existing_icon = DEFAULT_ICON_DIR / Path(existing_icon_path).name
        if existing_icon.exists():
            return existing_icon_path

    library_id = int(row["id"])
    library_name = row["name"] or f"Library {library_id}"
    source_photo = row["location_photo_path"] or row["books_photo_path"] or row["photo_path"]
    return create_library_icon(library_id, library_name, source_photo)


def load_libraries(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            l.id,
            l.name,
            COALESCE(l.box_type, 'library') AS box_type,
            l.description,
            l.latitude,
            l.longitude,
            l.location_source,
            l.location_confidence,
            l.place_clues,
            l.photo_path,
            l.books_photo_path,
            l.location_photo_path,
            l.icon_path,
            l.charter_number,
            l.charter_lookup_status,
            l.charter_record_checked_at,
            l.charter_record_distance_miles,
            l.charter_record_json,
            l.created_at,
            COUNT(b.id) AS book_count,
            GROUP_CONCAT(b.title, '||') AS sample_books
        FROM libraries l
        LEFT JOIN books b
            ON b.library_id = l.id
           AND COALESCE(b.status, 'active') = 'active'
        GROUP BY l.id
        ORDER BY l.id ASC
        """
    ).fetchall()

    libraries: list[dict[str, Any]] = []
    for row in rows:
        sample_books = [title for title in (row["sample_books"] or "").split("||") if title][:5]
        official_address = format_official_address(row["charter_record_json"])
        icon_path = ensure_library_icon(row)
        libraries.append(
            {
                "id": int(row["id"]),
                "csn": f"CSN-{int(row['id'])}",
                "name": row["name"] or f"Library {row['id']}",
                "box_type": normalize_box_type(row["box_type"]),
                "box_type_label": box_type_label(row["box_type"]),
                "description": row["description"] or "",
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "marker_latitude": row["latitude"],
                "marker_longitude": row["longitude"],
                "marker_location_source": row["location_source"] or "",
                "location_source": row["location_source"] or "",
                "location_confidence": row["location_confidence"],
                "place_clues": parse_place_clues(row["place_clues"]),
                "charter_number": row["charter_number"] or "",
                "charter_lookup_status": row["charter_lookup_status"] or "",
                "charter_record_checked_at": row["charter_record_checked_at"] or "",
                "charter_record_distance_miles": row["charter_record_distance_miles"],
                "official_address": official_address,
                "location_label": official_address or "",
                "icon_url": icon_path,
                "book_count": int(row["book_count"] or 0),
                "sample_books": sample_books,
                "created_at": row["created_at"] or "",
            }
        )

    return libraries


def load_books(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            id,
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
            created_at
        FROM books
        WHERE COALESCE(status, 'active') = 'active'
        ORDER BY library_id ASC, title COLLATE NOCASE ASC
        """
    ).fetchall()

    return [
        {
            "id": int(row["id"]),
            "library_id": int(row["library_id"]),
            "title": row["title"] or "",
            "author": row["author"] or "",
            "isbn": row["isbn"] or "",
            "publisher": row["publisher"] or "",
            "published_year": row["published_year"] or "",
            "genre": row["genre"] or "",
            "format": row["format"] or "",
            "condition": row["condition"] or "",
            "confidence": row["confidence"],
            "notes": row["notes"] or "",
            "created_at": row["created_at"] or "",
        }
        for row in rows
    ]


def export_pages_data(db_path: Path = DEFAULT_DB_PATH, output_path: Path = DEFAULT_OUTPUT_PATH) -> dict[str, Any]:
    db_path = Path(db_path)
    output_path = Path(output_path)

    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_export_schema(connection)
        libraries = load_libraries(connection)
        books = load_books(connection)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "libraries": len(libraries),
            "books": len(books),
        },
        "privacy": {
            "photos_included": False,
            "derived_icons_included": True,
            "note": "Original and uploaded photos are intentionally omitted. The site only includes small 144x144 derived library icons.",
        },
        "libraries": libraries,
        "books": books,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload["counts"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a static JSON snapshot for the GitHub Pages site.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite database.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Destination atlas-data.json path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    counts = export_pages_data(args.db, args.output)
    print(f"Exported {counts['libraries']} libraries and {counts['books']} books to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
