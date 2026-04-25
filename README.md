# Little Library Atlas

Little Library Atlas is a lightweight prototype for cataloging sidewalk mini-libraries from a photo and making nearby-book lookup possible from one shared database.

## What it does

- Takes a library photo from a browser file picker or phone camera.
- Pulls geolocation from photo EXIF GPS when it exists.
- Falls back to browser geolocation when the user allows it.
- Uses the OpenAI Responses API to extract visible books and metadata into JSON.
- Lets a human review and edit the draft before saving.
- Stores libraries and books in a central SQLite database file.
- Searches the database by title, author, or ISBN and ranks matches by distance.

## Project layout

- [app.py](app.py)
- [static/index.html](static/index.html)
- [static/styles.css](static/styles.css)
- [static/app.js](static/app.js)

## Run it

1. Set an OpenAI key if you want automated book extraction.

```powershell
$env:OPENAI_API_KEY="your-key-here"
```

2. Start the app.

```powershell
python app.py
```

3. Open `http://127.0.0.1:8000`.

## Ingest a local photo

The CLI ingest path is useful when you already have a photo on disk and a reviewed metadata JSON file.

```powershell
python scripts\ingest_photo.py "C:\Users\xliup\Downloads\PXL_20260328_161848034 (1).jpg"
```

The default metadata file is [samples/blue_little_library_books.json](samples/blue_little_library_books.json). The script copies the photo into `data/uploads`, extracts EXIF GPS, inserts the library and books into SQLite, then runs a verification search.

## Notes

- If `OPENAI_API_KEY` is not set, the app still works in manual review mode.
- The default model is `gpt-4.1-mini`. Set `OPENAI_VISION_MODEL` if you want a different OpenAI vision-capable model.
- The shared database lives at `data/little_library_atlas.db`.
- This prototype uses SQLite for simplicity. For multi-server production deployment, move the same schema to Postgres.
