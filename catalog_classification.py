"""Source-backed work classifications; never invent edition-specific call numbers."""
from __future__ import annotations
import json
import re
import sqlite3
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from book_categories import fill_missing_categories, match_category_documents, apply_category

FIELDS = ("ddc_numbers", "lcc_numbers", "classification_status", "classification_sources", "classification_checked_at")

def ensure_classification_schema(connection):
    columns = {r[1] for r in connection.execute("PRAGMA table_info(books)")}
    for name, definition in {
        "ddc_numbers": "TEXT NOT NULL DEFAULT '[]'",
        "lcc_numbers": "TEXT NOT NULL DEFAULT '[]'",
        "classification_status": "TEXT NOT NULL DEFAULT 'pending'",
        "classification_sources": "TEXT NOT NULL DEFAULT '[]'",
        "classification_checked_at": "TEXT NOT NULL DEFAULT ''",
    }.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE books ADD COLUMN {name} {definition}")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS classification_cache (
            cache_key TEXT PRIMARY KEY, response_json TEXT NOT NULL,
            checked_at TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS reset_book_classification
        AFTER UPDATE OF title, author, isbn ON books
        WHEN NEW.title IS NOT OLD.title OR NEW.author IS NOT OLD.author OR NEW.isbn IS NOT OLD.isbn
        BEGIN
            UPDATE books SET ddc_numbers='[]', lcc_numbers='[]',
                classification_status='pending', classification_sources='[]',
                classification_checked_at='' WHERE id=NEW.id;
        END;
    """)


def public_classification(row):
    result = {name: row[name] or "" for name in FIELDS}
    for name in ("ddc_numbers", "lcc_numbers", "classification_sources"):
        try:
            value = json.loads(result[name] or '[]')
            result[name] = value if isinstance(value, list) else []
        except (ValueError, TypeError):
            result[name] = []
    return result


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value or '')).casefold()
    return ' '.join(re.findall(r'[^\W_]+', value, re.UNICODE))


def clean_lcc(value):
    # Search returns Solr sortable notation, e.g. QA-0076.73000000.P98.
    value = re.sub(r'^([A-Z]{1,3})-0*(\d+)(?:\.(\d+))?',
        lambda m: m[1] + str(int(m[2])) +
        (('.' + m[3].rstrip('0')) if m[3] and m[3].rstrip('0') else ''), str(value))
    return value.strip()


def match_classification(book, documents):
    title, author = normalized(book['title']), normalized(book['author'])
    candidates = [doc for doc in documents
        if normalized(doc.get('title')) == title and author
        and author in [normalized(a) for a in doc.get('author_name', [])]]
    # Multiple works with the same title/author still need human review.
    unique = {doc.get('key'): doc for doc in candidates}
    if len(unique) != 1:
        return dict(ddc_numbers=[], lcc_numbers=[], classification_status='needs_review', classification_sources=[])
    doc = next(iter(unique.values()))
    ddc = sorted({str(v).strip() for v in doc.get('ddc', []) if re.fullmatch(r'\d{3}(?:\.\d+)?', str(v).strip())})
    lcc = sorted({clean_lcc(v) for v in doc.get('lcc', []) if re.fullmatch(r'[A-Z]{1,3}\d.*', clean_lcc(v))})
    key = str(doc.get('key', ''))
    sources = ['https://openlibrary.org' + key] if re.fullmatch(r'/works/OL\d+W', key) else []
    if not sources:
        ddc, lcc = [], []
    return dict(ddc_numbers=ddc, lcc_numbers=lcc,
        classification_status='matched_work' if ddc or lcc else 'needs_review',
        classification_sources=sources)


def fetch_documents(books, fields="key,title,author_name,ddc,lcc,subject"):
    def quoted(value):
        return '"' + re.sub(r'["\\]', ' ', value) + '"'
    query = ' OR '.join('(title:' + quoted(book['title']) + ' AND author:' + quoted(book['author']) + ')' for book in books)
    params = dict(q='(' + query + ')', fields=fields, limit=100)
    docs = []
    for offset in range(0, 1000, 100):
        params['offset'] = offset
        request = urllib.request.Request('https://openlibrary.org/search.json?' + urllib.parse.urlencode(params),
            headers={'User-Agent': 'CivitasLibrary/1.0 (civitaslibrary@gmail.com)'})
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
        total = data.get('numFound', data.get('num_found', 0))
        if total > 500:
            if len(books) == 1:
                return []  # Too broad to establish a safe match.
            midpoint = len(books) // 2
            time.sleep(1.05)
            first = fetch_documents(books[:midpoint], fields)
            time.sleep(1.05)
            return first + fetch_documents(books[midpoint:], fields)
        docs.extend(data.get('docs', []))
        if offset + 100 >= data.get('numFound', data.get('num_found', 0)):
            return docs
        time.sleep(1.05)
    raise ValueError('Too many candidate works; narrow the lookup before assigning classifications')


def enrich_pending(db_path, limit=20, fetcher=fetch_documents):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        ensure_classification_schema(connection)
        rows = connection.execute("SELECT id,title,author,isbn FROM books WHERE classification_status='pending' ORDER BY id LIMIT ?", (limit,)).fetchall()
        if not rows:
            return 0
        cached, uncached = {}, []
        for row in rows:
            key = normalized(row['title']) + '|' + normalized(row['author'])
            entry = connection.execute('SELECT response_json FROM classification_cache WHERE cache_key=?', (key,)).fetchone()
            if entry:
                cached[row['id']] = json.loads(entry[0])
            elif row['author']:
                uncached.append(row)
            else:
                cached[row['id']] = match_classification(row, [])
        connection.commit()
        documents = fetcher(list({(row['title'], row['author']): dict(row) for row in uncached}.values())) if uncached else []
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        fill_missing_categories(connection)
        for row in rows:
            result = cached.get(row['id']) or match_classification(row, documents)
            if row['id'] not in cached:
                category, sources = match_category_documents(dict(row), documents)
                if category:
                    result['category'] = category
                    result['category_sources'] = sources
            # Recheck identity: metadata could have changed while the network request ran.
            connection.execute("""UPDATE books SET ddc_numbers=?, lcc_numbers=?, classification_status=?,
                classification_sources=?, classification_checked_at=?
                WHERE id=? AND title=? AND COALESCE(author,'')=? AND COALESCE(isbn,'')=? AND classification_status='pending'""",
                (json.dumps(result['ddc_numbers']), json.dumps(result['lcc_numbers']), result['classification_status'],
                 json.dumps(result['classification_sources']), now, row['id'], row['title'], row['author'] or '', row['isbn'] or ''))
            if result.get('category'):
                apply_category(connection, dict(row), result['category'], 'Matched catalog subjects', json.dumps(result.get('category_sources', [])))
            key = normalized(row['title']) + '|' + normalized(row['author'])
            connection.execute('INSERT OR REPLACE INTO classification_cache VALUES(?,?,?)', (key, json.dumps(result), now))
        fill_missing_categories(connection)
        connection.commit()
        return len(rows)
    finally:
        connection.close()
