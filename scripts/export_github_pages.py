from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "little_library_atlas.db"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "docs" / "atlas-data.json"


def parse_place_clues(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()] if isinstance(parsed, list) else []


def load_libraries(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            l.id,
            l.name,
            l.description,
            l.latitude,
            l.longitude,
            l.location_source,
            l.location_confidence,
            l.place_clues,
            l.created_at,
            COUNT(b.id) AS book_count,
            GROUP_CONCAT(b.title, '||') AS sample_books
        FROM libraries l
        LEFT JOIN books b ON b.library_id = l.id
        GROUP BY l.id
        ORDER BY l.id ASC
        """
    ).fetchall()

    libraries: list[dict[str, Any]] = []
    for row in rows:
        sample_books = [title for title in (row["sample_books"] or "").split("||") if title][:5]
        libraries.append(
            {
                "id": int(row["id"]),
                "name": row["name"] or f"Library {row['id']}",
                "description": row["description"] or "",
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "location_source": row["location_source"] or "",
                "location_confidence": row["location_confidence"],
                "place_clues": parse_place_clues(row["place_clues"]),
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
            "note": "Original and uploaded photos are intentionally omitted from the static GitHub Pages export.",
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
