from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_PATH = ROOT_DIR / "docs" / "atlas-data.json"

FORBIDDEN_TEXT = (
    "data/uploads/",
    "\\data\\uploads\\",
)

FORBIDDEN_KEYS = {
    "photo_path",
    "books_photo_path",
    "location_photo_path",
    "photo_url",
    "books_photo_url",
    "location_photo_url",
    "upload_path",
    "original_filename",
}


def walk_json(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(walk_json(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(walk_json(child, f"{path}[{index}]"))
    return items


def validate_public_export(export_path: Path = DEFAULT_EXPORT_PATH, site_root: Path | None = None) -> list[str]:
    export_path = Path(export_path)
    site_root = Path(site_root) if site_root else export_path.parent
    errors: list[str] = []

    try:
        raw_text = export_path.read_text(encoding="utf-8")
    except OSError as error:
        return [f"Could not read {export_path}: {error}"]

    for forbidden in FORBIDDEN_TEXT:
        if forbidden in raw_text:
            errors.append(f"Public export contains forbidden raw upload path text: {forbidden}")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as error:
        return errors + [f"Invalid JSON in {export_path}: {error}"]

    libraries = payload.get("libraries")
    books = payload.get("books")
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}

    if not isinstance(libraries, list):
        errors.append("Public export must contain a libraries array.")
        libraries = []
    if not isinstance(books, list):
        errors.append("Public export must contain a books array.")
        books = []

    if counts.get("libraries") != len(libraries):
        errors.append(f"Library count mismatch: counts.libraries={counts.get('libraries')} actual={len(libraries)}")
    if counts.get("books") != len(books):
        errors.append(f"Book count mismatch: counts.books={counts.get('books')} actual={len(books)}")
    if privacy.get("photos_included") is not False:
        errors.append("privacy.photos_included must be false for the public export.")

    for path, value in walk_json(payload):
        if path.rsplit(".", 1)[-1] in FORBIDDEN_KEYS:
            errors.append(f"Public export contains forbidden photo/upload key: {path}")
        if isinstance(value, str):
            normalized = value.replace("\\", "/")
            if "data/uploads/" in normalized:
                errors.append(f"Public export contains raw upload path at {path}: {value}")

    for index, library in enumerate(libraries):
        if not isinstance(library, dict):
            errors.append(f"libraries[{index}] must be an object.")
            continue
        icon_url = str(library.get("icon_url") or "").strip()
        if not icon_url:
            continue
        normalized_icon = icon_url.replace("\\", "/").lstrip("/")
        if normalized_icon.startswith("data/uploads/"):
            errors.append(f"libraries[{index}].icon_url points at raw uploads: {icon_url}")
            continue
        if normalized_icon.startswith("library-icons/") and not (site_root / normalized_icon).exists():
            errors.append(f"libraries[{index}].icon_url does not exist under the site root: {icon_url}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the public GitHub Pages atlas export.")
    parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT_PATH, help="Path to docs/atlas-data.json.")
    parser.add_argument("--site-root", type=Path, default=None, help="Static site root. Defaults to export parent.")
    args = parser.parse_args()

    errors = validate_public_export(args.export, args.site_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Public export validation passed: {args.export}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
