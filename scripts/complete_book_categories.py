"""Complete missing genres conservatively and preserve an audit trail."""
import json,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from book_categories import fill_missing_categories, apply_category, match_category_documents
from catalog_classification import fetch_documents


def main():
    with app.get_connection() as c:
        count=fill_missing_categories(c)
        books=[dict(r) for r in c.execute("SELECT * FROM books WHERE trim(coalesce(genre,''))='' AND trim(coalesce(author,''))!=''")]
    folder=ROOT/'data/uploads/category-repair-20261020'
    folder.mkdir(exist_ok=True,parents=True)
    for start in range(0,len(books),20):
        batch=books[start:start+20]
        import hashlib
        key=hashlib.sha256(json.dumps([(b['title'],b['author']) for b in batch]).encode()).hexdigest()[:12]
        path=folder/f'subjects-{key}.json'
        if path.exists(): docs=json.loads(path.read_text(encoding='utf-8'))
        else:
            docs=fetch_documents(batch,fields='key,title,author_name,ddc,lcc,subject')
            path.write_text(json.dumps(docs,indent=2)+'\n',encoding='utf-8')
        with app.get_connection() as c:
            for book in batch:
                category,sources=match_category_documents(book,docs)
                if category:
                    count+=apply_category(c,book,category,'Title and author matched catalog subjects; broad category consensus',json.dumps(sources))
        print(f'Checked {min(start+20,len(books))}/{len(books)} subject candidates',flush=True)
        time.sleep(1.05)
    with app.get_connection() as c:
        remaining=[dict(r) for r in c.execute("SELECT id,title,author FROM books WHERE trim(coalesce(genre,''))=''")]
    (folder/'remaining-review.json').write_text(json.dumps(remaining,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'filled_this_pass':count,'remaining':len(remaining)}))

if __name__=='__main__': main()
