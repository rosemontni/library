import json
import unittest
from unittest.mock import patch
import app
from book_categories import infer_category, match_category_documents, fill_missing_categories
from tests import test_reading_library

class CategoryInferenceTests(unittest.TestCase):
    def test_clear_titles_and_consistent_classifications_only(self):
        for title,expected in [('Intermediate Algebra','Mathematics'),('Careers in Health Care','Careers'),("The Business Writer's Handbook",'Writing & Language'),('The Harvest',''),('Tree',''),('Career of Evil',''),('The Dictionary of Lost Words','')]:
            genre,_=infer_category(dict(title=title,ddc_numbers='[]',lcc_numbers='[]'))
            self.assertEqual(genre,expected)
        self.assertEqual(infer_category(dict(title='Unknown',ddc_numbers='["813.54"]',lcc_numbers='[]'))[0],'Fiction')
        self.assertEqual(infer_category(dict(title='Unknown',ddc_numbers='["813.54","371.3"]',lcc_numbers='[]'))[0],'')

    def test_matching_ignores_empty_subjects_but_rejects_disagreement(self):
        book=dict(title='Test Book',author='Jane Smith')
        doc=dict(key='/works/OL123W',title='Test Book',author_name=['Jane Smith'],subject=['Fiction'])
        self.assertEqual(match_category_documents(book,[doc,dict(doc,subject=[])])[0],'Fiction')
        self.assertEqual(match_category_documents(book,[doc,dict(doc,subject=['Business management'])])[0],'')
        self.assertEqual(match_category_documents(dict(book,author='Other Author'),[doc])[0],'')

class CategoryStorageTests(unittest.TestCase):
    setUp = test_reading_library.ReadingLibraryTests.setUp
    tearDown = test_reading_library.ReadingLibraryTests.tearDown
    def test_new_intake_gets_category_and_blank_updates_preserve_it(self):
        with patch.object(app,'refresh_library_map'),patch.object(app,'refresh_pages_data'):
            library=app.insert_library({'library_name':'Math Shelf','geolocation':{'latitude':41,'longitude':-75,'source':'photo_exif'},'books':[{'title':'Intermediate Algebra'}]})
            self.assertEqual(app.list_library_books(library)[0]['genre'],'Mathematics')
            self.assertEqual(app.search_books('Mathematics',None,None,None)[0]['title'],'Intermediate Algebra')
            app.insert_library({'library_id':library,'library_name':'Math Shelf','geolocation':{'latitude':41,'longitude':-75,'source':'photo_exif'},'books':[{'title':'Intermediate Algebra'}]})
            self.assertEqual(app.list_library_books(library)[0]['genre'],'Mathematics')
            with app.get_connection() as c:
                self.assertEqual(fill_missing_categories(c),0)
                self.assertEqual(c.execute('SELECT genre FROM book_category_assignments WHERE book_id=(SELECT id FROM books WHERE library_id=?)',(library,)).fetchone()[0],'Mathematics')

    def test_subject_lookup_completes_new_book_category(self):
        from catalog_classification import enrich_pending
        with patch.object(app,'refresh_library_map'),patch.object(app,'refresh_pages_data'):
            library=app.insert_library({'library_name':'Stories','geolocation':{'latitude':42,'longitude':-75,'source':'photo_exif'},'books':[{'title':'Test Story','author':'Jane Smith'}]})
            enrich_pending(app.DB_PATH,fetcher=lambda books:[dict(key='/works/OL123W',title='Test Story',author_name=['Jane Smith'],subject=['Fiction'])])
            self.assertEqual(app.list_library_books(library)[0]['genre'],'Fiction')
