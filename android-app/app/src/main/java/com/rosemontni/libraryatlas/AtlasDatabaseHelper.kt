package com.rosemontni.libraryatlas

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

class AtlasDatabaseHelper(context: Context) : SQLiteOpenHelper(context, DATABASE_NAME, null, DATABASE_VERSION) {
    override fun onConfigure(db: SQLiteDatabase) {
        db.setForeignKeyConstraintsEnabled(true)
    }

    override fun onCreate(db: SQLiteDatabase) {
        createSchema(db)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        var migratedVersion = oldVersion
        db.beginTransaction()
        try {
            if (migratedVersion < 1) {
                createSchema(db)
                migratedVersion = 1
            }
            if (migratedVersion < 2) {
                migrateToVersion2(db)
                migratedVersion = 2
            }

            require(migratedVersion == newVersion) {
                "Unsupported database migration from $oldVersion to $newVersion"
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    private fun createSchema(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE IF NOT EXISTS libraries (
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
            CREATE TABLE IF NOT EXISTS books (
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

        db.execSQL("CREATE INDEX IF NOT EXISTS idx_books_library_id ON books(library_id)")
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)")
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn)")
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_libraries_coords ON libraries(latitude, longitude)")
    }

    private fun migrateToVersion2(db: SQLiteDatabase) {
        // Version 2 establishes a non-destructive migration baseline.
        createSchema(db)
    }

    companion object {
        private const val DATABASE_NAME = "little_library_atlas_android.db"
        private const val DATABASE_VERSION = 2
    }
}
