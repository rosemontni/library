package com.rosemontni.libraryatlas

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

class AtlasDatabaseHelper(context: Context) : SQLiteOpenHelper(context, DATABASE_NAME, null, DATABASE_VERSION) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE libraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                latitude REAL,
                longitude REAL,
                location_source TEXT NOT NULL,
                location_confidence REAL NOT NULL DEFAULT 0,
                photo_path TEXT,
                place_clues TEXT,
                created_at INTEGER NOT NULL
            )
            """.trimIndent()
        )

        db.execSQL(
            """
            CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                author TEXT,
                isbn TEXT,
                publisher TEXT,
                published_year TEXT,
                genre TEXT,
                format TEXT,
                condition TEXT,
                confidence REAL,
                notes TEXT,
                search_blob TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
            )
            """.trimIndent()
        )

        db.execSQL("CREATE INDEX idx_books_library_id ON books(library_id)")
        db.execSQL("CREATE INDEX idx_books_title ON books(title)")
        db.execSQL("CREATE INDEX idx_books_isbn ON books(isbn)")
        db.execSQL("CREATE INDEX idx_libraries_coords ON libraries(latitude, longitude)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS books")
        db.execSQL("DROP TABLE IF EXISTS libraries")
        onCreate(db)
    }

    companion object {
        private const val DATABASE_NAME = "little_library_atlas_android.db"
        private const val DATABASE_VERSION = 1
    }
}
