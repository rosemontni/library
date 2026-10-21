import gc
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
from catalog_classification import ensure_classification_schema, enrich_pending, match_classification, clean_lcc
from scripts.export_github_pages import export_pages_data

DOC = {'key':'/works/OL123W', 'title':'Test Book', 'author_name':['Jane Smith'],
       'ddc':['635.9', '[Fic]'], 'lcc':['SB-0450.00000000.S65 2020']}

class ClassificationTests(unittest.TestCase):
    def test_matching_requires_exact_title_author_and_unique_work(self):
        book = {'title':'Test Book', 'author':'Jane Smith'}
        match = match_classification(book, [DOC])
        self.assertEqual(match['ddc_numbers'], ['635.9'])
        self.assertEqual(match['lcc_numbers'], ['SB450.S65 2020'])
        self.assertEqual(match['classification_status'], 'matched_work')
        for title, author, docs in [('Test Book','', [DOC]), ('Test','Jane Smith',[DOC]),
                ('Test Book','Other Smith',[DOC]), ('Test Book','Jane Smith',[DOC,dict(DOC,key='/works/OL456W')])]:
            self.assertEqual(match_classification({'title':title,'author':author},docs)['classification_status'], 'needs_review')

    def test_solr_notation_preserves_significant_decimals(self):
        self.assertEqual(clean_lcc('QA-0076.73000000.P98'), 'QA76.73.P98')

    def test_old_schema_migrates_and_new_records_are_pending(self):
        connection=sqlite3.connect(':memory:')
        connection.execute('CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,author TEXT,isbn TEXT)')
        connection.execute("INSERT INTO books VALUES(1,'Old','Author','')")
        ensure_classification_schema(connection)
        ensure_classification_schema(connection)
        connection.execute("INSERT INTO books(id,title) VALUES(2,'New')")
        self.assertEqual(connection.execute('SELECT classification_status FROM books ORDER BY id').fetchall(), [('pending',),('pending',)])
        connection.close()

    def test_enrichment_search_export_cache_and_metadata_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.multiple(app, DATA_DIR=root, UPLOADS_DIR=root/'uploads',DB_PATH=root/'atlas.db'), patch.object(app,'should_refresh_library_map',return_value=False), patch.object(app,'refresh_pages_data'):
                app.initialize_database()
                library=app.insert_library({'library_name':'Test', 'geolocation':{'latitude':39,'longitude':-77,'source':'photo_exif'}, 'books':[{'title':'Test Book','author':'Jane Smith'}]})
                self.assertEqual(enrich_pending(app.DB_PATH,fetcher=lambda titles:[DOC]),1)
                book=app.search_books('635.9',None,None,None)[0]
                self.assertEqual(book['lcc_numbers'],['SB450.S65 2020'])
                self.assertEqual(app.list_library_books(library)[0]['classification_status'],'matched_work')
                export_pages_data(app.DB_PATH,root/'atlas.json')
                data=json.loads((root/'atlas.json').read_text(encoding='utf-8'))
                self.assertEqual(data['books'][0]['ddc_numbers'],['635.9'])
                app.initialize_database()
                self.assertEqual(app.list_library_books(library)[0]['ddc_numbers'],['635.9'])
                with app.get_connection() as connection:
                    connection.execute("INSERT INTO books(library_id,title,author,isbn,search_blob) VALUES(?, 'Test Book','Jane Smith','','test')", (library,))
                self.assertEqual(enrich_pending(app.DB_PATH,fetcher=lambda titles:self.fail('cache should avoid network')),1)
                with app.get_connection() as connection:
                    connection.execute("UPDATE books SET title='Changed Book' WHERE id=?",(book['book_id'],))
                changed=next(b for b in app.list_library_books(library) if b['book_id']==book['book_id'])
                self.assertEqual(changed['classification_status'],'pending')
                self.assertEqual(changed['ddc_numbers'],[])
                with self.assertRaises(OSError):
                    enrich_pending(app.DB_PATH,fetcher=lambda titles: (_ for _ in ()).throw(OSError('offline')))
                self.assertEqual(next(b for b in app.list_library_books(library) if b['book_id']==book['book_id'])['classification_status'],'pending')
            gc.collect()
