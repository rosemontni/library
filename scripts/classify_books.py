"""Resume source-backed classification of pending books without paid API calls."""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from catalog_classification import enrich_pending, ensure_classification_schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT/'data/little_library_atlas.db')
    parser.add_argument('--retry-review', action='store_true')
    args = parser.parse_args()
    with sqlite3.connect(args.db) as connection:
        ensure_classification_schema(connection)
        if args.retry_review:
            connection.execute("UPDATE books SET classification_status='pending' WHERE classification_status='needs_review'")
            connection.execute('DELETE FROM classification_cache')
    processed = 0
    while True:
        count = enrich_pending(args.db)
        if not count:
            break
        processed += count
        print(f'Processed {processed} book records', flush=True)
        time.sleep(1.05)
    with sqlite3.connect(args.db) as connection:
        print(json.dumps(dict(connection.execute('SELECT classification_status,COUNT(*) FROM books GROUP BY classification_status'))))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
