"""Conservative category completion, independent of exact edition call numbers."""
import json
import re
from datetime import datetime, timezone

def infer_category(book):
    title = str(book['title'] or '').casefold()
    rules = [
        (r"\b(careers? (?:in|development|guide|advising)|opportunities.*careers|opportunities for recreational therapists)\b", 'Careers'),
        (r"\b(education and related services|academic advising|college campus|graduate school|college of literature|university.*bulletin|university course bulletin|fiske guide|undergraduate advising|psychology the major|scholarship reconsidered|school of graduate studies)\b", 'Education'),
        (r"\b(dermatologic|bone morphogenetic|otolaryngology|biomedical|origin of cancer|unequal burden of cancer|nursing homes|cardiovascular|geriatrics|biosafety|human health|microsporidia|microsporidiosis|rickettsial|hepatitis|mental health)\b", 'Health & Medicine'),
        (r"\b(psychologist|psychology|behavioral science)\b", 'Psychology'),
        (r"\b(social work|human services)\b", 'Social Sciences'),
        (r"\b(algebra|calculus|geometry)\b", 'Mathematics'),
        (r"\b(genetically|genetic ends|chemical building blocks|laboratory animals|historical sciences)\b", 'Science'),
        (r"\b(international space station)\b", 'Science / Space'),
        (r"\b(webster|merriam|roget).*\b(dictionary|thesaurus)\b", 'Reference'),
        (r"\b(handbook of english|business writ(?:ing|er)|business writer|style manual|elements of style|grammatically correct|using sources effectively)\b", 'Writing & Language'),
        (r"\b(learning spanish)\b", 'Languages'),
        (r"\b(public relations|leadership|effective teams|marketing|organized innovation)\b", 'Business'),
        (r"\b(federal manager|public papers of the presidents|house of representatives telephone directory)\b", 'Government'),
        (r"\b(sharepoint)\b", 'Computing'),
        (r"\b(chemical and biological warfare)\b", 'Military History'),
        (r"\b(sticker book|disney.*stories|who was sacagawea|nancy drew.*mystery|nancy drew.*staircase|nancy drew.*shadow ranch|nancy drew.*lilac inn)\b", 'Children'),
        (r"^reader.s digest,", 'Magazines'),
        (r"\b(handbook for historians)\b", 'History'),
        (r"\b(conducting a survey|global culture)\b", 'Social Sciences'),
        (r"\b(science of yoga)\b", 'Health & Fitness'),
        (r"\b(donut mystery|bounty hunter)\b", 'Mystery' if 'mystery' in title else 'Western'),
        (r"\b(baby brothers and baby sisters)\b", 'Children / Family'),
    ]
    for pattern, genre in rules:
        if re.search(pattern,title):
            return genre, 'Explicit subject or collection in title'
    genres=[]
    for value in json.loads(book['ddc_numbers'] or '[]'):
        if re.fullmatch(r'\d{3}(?:\.\d+)?',value):
            code=int(value[:3])
            if code in (813,823,833,843,853,863,873,883): genre='Fiction'
            elif 370<=code<380: genre='Education'
            elif 610<=code<620: genre='Health & Medicine'
            elif 150<=code<160: genre='Psychology'
            elif 500<=code<600: genre='Science'
            elif 650<=code<660: genre='Business'
            else: continue
            genres.append(genre)
    if genres and len(set(genres))==1:
        return genres[0], 'Consistent Dewey subject classifications'
    lcc=json.loads(book['lcc_numbers'] or '[]')
    if lcc and all(re.match(r'P[RSQT]\d',code) for code in lcc):
        return 'Literature', 'Literary work matched to LCC author classification'
    return '', ''


def fill_missing_categories(connection, library_id=None):
    connection.execute("""CREATE TABLE IF NOT EXISTS book_category_assignments (
        book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
        genre TEXT NOT NULL, basis TEXT NOT NULL, source TEXT NOT NULL,
        assigned_at TEXT NOT NULL
    )""")
    sql="SELECT * FROM books WHERE trim(coalesce(genre,''))=''"
    args=()
    if library_id is not None:
        sql+=' AND library_id=?';args=(library_id,)
    count=0
    for row in connection.execute(sql,args).fetchall():
        book=dict(row)
        genre,basis=infer_category(book)
        if genre:
            apply_category(connection,book,genre,basis,book.get('classification_sources') or '')
            count+=1
    return count


def apply_category(connection, book, genre, basis, source=''):
    # Only fill gaps: an existing reviewed category always takes precedence.
    changed=connection.execute("UPDATE books SET genre=?, search_blob=trim(coalesce(search_blob,'') || ' ' || ?) WHERE id=? AND title=? AND coalesce(author,'')=? AND trim(coalesce(genre,''))=''",(genre,genre.casefold(),book['id'],book['title'],book.get('author') or '')).rowcount
    if changed:
        connection.execute('INSERT OR REPLACE INTO book_category_assignments VALUES(?,?,?,?,?)',
            (book['id'],genre,basis,source,datetime.now(timezone.utc).isoformat(timespec='seconds')))
    return changed


def category_from_subjects(subjects):
    text=' | '.join(str(s).casefold() for s in subjects)
    for pattern,category in [
        (r'\b(juvenile fiction|children.s fiction|picture books|children.s stories)\b','Children'),
        (r'\b(fantasy fiction|fantasy)\b','Fantasy'),
        (r'\b(detective|mystery fiction|mystery and detective)\b','Mystery'),
        (r'\b(science fiction)\b','Science Fiction'),
        (r'\b(fiction)\b','Fiction'),
        (r'\b(education|universities|higher education and related services|academic advising)\b','Education'),
        (r'\b(business|management|leadership|success)\b','Business'),
        (r'\b(english language|business writing|authorship)\b','Writing & Language'),
        (r'\b(sociology|social conditions|social sciences)\b','Social Sciences'),
        (r'\b(yoga|physical fitness)\b','Health & Fitness'),
        (r'\b(gardening|gardens|horticulture)\b','Gardening'),
        (r'\b(christianity|christian life|bible)\b','Religion'),
        (r'\b(art|artists|sculpture)\b','Art'),
        (r'\b(history)\b','History'),
    ]:
        if re.search(pattern,text): return category
    return ''


def match_category_documents(book, documents):
    from catalog_classification import normalized
    def title_key(value):
        # Series labels are not needed for broad category matching.
        value=re.sub(r'\s*\([^)]*\)\s*$', '', value)
        value=re.sub(r'^(the|a|an)\s+', '', value, flags=re.I)
        return normalized(value).replace(' ', '')
    title=title_key(book['title'])
    author=str(book.get('author') or '').strip()
    if not author: return '', []
    author_parts=[normalized(re.sub(r'\([^)]*\)','',a)).strip() for a in author.split(';')]
    matches=[]
    for doc in documents:
        if title_key(doc.get('title',''))!=title and title_key(doc.get('title','').split(':',1)[0])!=title: continue
        names=[normalized(' '.join(reversed(n.split(', ',1))) if ', ' in n else n) for n in doc.get('author_name',[])]
        if not any(part and (part in names or (len(part.split())==1 and part in [n.split()[-1] for n in names if n])) for part in author_parts): continue
        matches.append(doc)
    if not matches: return '', []
    matches=[doc for doc in matches if doc.get('subject')]
    if not matches: return '', []
    categories=[category_from_subjects(doc.get('subject',[])) for doc in matches]
    if any(not category for category in categories): return '', []
    genre=categories[0] if len(set(categories))==1 else ''
    if not genre and all(re.search(r'\bfiction\b',' | '.join(doc.get('subject',[])),re.I) for doc in matches): genre='Fiction'
    sources=['https://openlibrary.org'+doc['key'] for doc in matches if re.fullmatch(r'/works/OL\d+W',doc.get('key',''))]
    return (genre, sorted(set(sources))) if sources else ('', [])
