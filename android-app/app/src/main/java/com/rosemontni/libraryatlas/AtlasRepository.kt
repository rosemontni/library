package com.rosemontni.libraryatlas

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.core.content.FileProvider
import androidx.exifinterface.media.ExifInterface
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.Locale
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

class AtlasRepository(private val context: Context) {
    private val databaseHelper = AtlasDatabaseHelper(context)

    fun getStats(): CatalogStats {
        val db = databaseHelper.readableDatabase
        val libraryCount = db.rawQuery("SELECT COUNT(*) FROM libraries", null).use { cursor ->
            cursor.moveToFirst()
            cursor.getInt(0)
        }
        val bookCount = db.rawQuery("SELECT COUNT(*) FROM books", null).use { cursor ->
            cursor.moveToFirst()
            cursor.getInt(0)
        }
        return CatalogStats(libraryCount, bookCount)
    }

    fun getLibraries(): List<LibrarySummary> {
        val db = databaseHelper.readableDatabase
        val libraries = mutableListOf<LibrarySummary>()
        db.rawQuery(
            """
            SELECT l.id, l.name, l.description, l.latitude, l.longitude, l.photo_path,
                   l.location_source, l.location_confidence, COUNT(b.id) AS book_count
            FROM libraries l
            LEFT JOIN books b ON b.library_id = l.id
            GROUP BY l.id
            ORDER BY l.created_at DESC
            """.trimIndent(),
            null
        ).use { cursor ->
            while (cursor.moveToNext()) {
                libraries += LibrarySummary(
                    id = cursor.getLong(0),
                    name = cursor.getString(1),
                    description = cursor.getString(2) ?: "",
                    latitude = cursor.getNullableDouble(3),
                    longitude = cursor.getNullableDouble(4),
                    photoPath = cursor.getString(5),
                    locationSource = cursor.getString(6) ?: "manual",
                    locationConfidence = cursor.getFloat(7),
                    bookCount = cursor.getInt(8),
                )
            }
        }
        return libraries
    }

    fun saveLibrary(draft: LibraryDraft): Long {
        val titleCount = draft.books.count { it.title.isNotBlank() }
        require(titleCount > 0) { "Add at least one book before saving." }

        val latitude = draft.latitude.toDoubleOrNull()
        val longitude = draft.longitude.toDoubleOrNull()
        val photoPath = draft.photoUri.takeIf { it.isNotBlank() }?.let { copyPhotoToPrivateStore(Uri.parse(it)) }
        val now = System.currentTimeMillis()
        val db = databaseHelper.writableDatabase

        db.beginTransaction()
        return try {
            val libraryValues = ContentValues().apply {
                put("name", draft.name.ifBlank { "Neighborhood Shelf" })
                put("description", draft.description)
                putNullableDouble("latitude", latitude)
                putNullableDouble("longitude", longitude)
                put("location_source", draft.locationSource)
                put("location_confidence", draft.locationConfidence.toDouble())
                put("photo_path", photoPath)
                put("place_clues", draft.placeClues)
                put("created_at", now)
            }

            val libraryId = db.insertOrThrow("libraries", null, libraryValues)

            draft.books
                .filter { it.title.isNotBlank() }
                .forEach { book ->
                    val values = ContentValues().apply {
                        put("library_id", libraryId)
                        put("title", book.title)
                        put("author", book.author)
                        put("isbn", book.isbn)
                        put("publisher", book.publisher)
                        put("published_year", book.publishedYear)
                        put("genre", book.genre)
                        put("format", book.format)
                        put("condition", book.condition)
                        put("confidence", book.confidence.toDouble())
                        put("notes", book.notes)
                        put(
                            "search_blob",
                            normalizeText(
                                listOf(
                                    book.title,
                                    book.author,
                                    book.isbn,
                                    book.publisher,
                                    book.genre,
                                    book.notes,
                                ).joinToString(" ")
                            )
                        )
                        put("created_at", now)
                    }
                    db.insertOrThrow("books", null, values)
                }

            db.setTransactionSuccessful()
            libraryId
        } finally {
            db.endTransaction()
        }
    }

    fun searchBooks(
        query: String,
        latitude: Double?,
        longitude: Double?,
        radiusMiles: Double,
    ): List<SearchResult> {
        val normalizedTerms = normalizeText(query)
            .split(" ")
            .filter { it.isNotBlank() }

        if (normalizedTerms.isEmpty()) {
            return emptyList()
        }

        val where = normalizedTerms.joinToString(" AND ") { "b.search_blob LIKE ?" }
        val args = normalizedTerms.map { "%$it%" }.toTypedArray()

        val db = databaseHelper.readableDatabase
        val results = mutableListOf<SearchResult>()
        db.rawQuery(
            """
            SELECT
                b.id,
                b.title,
                b.author,
                b.isbn,
                b.publisher,
                b.published_year,
                b.genre,
                b.format,
                b.condition,
                b.confidence,
                b.notes,
                l.id,
                l.name,
                l.description,
                l.latitude,
                l.longitude,
                l.photo_path,
                l.location_source,
                l.location_confidence
            FROM books b
            JOIN libraries l ON l.id = b.library_id
            WHERE $where
            ORDER BY b.confidence DESC, l.location_confidence DESC, b.title ASC
            """.trimIndent(),
            args
        ).use { cursor ->
            while (cursor.moveToNext()) {
                val library = LibrarySummary(
                    id = cursor.getLong(11),
                    name = cursor.getString(12),
                    description = cursor.getString(13) ?: "",
                    latitude = cursor.getNullableDouble(14),
                    longitude = cursor.getNullableDouble(15),
                    photoPath = cursor.getString(16),
                    locationSource = cursor.getString(17) ?: "manual",
                    locationConfidence = cursor.getFloat(18),
                    bookCount = 0,
                )

                val distance = if (latitude != null && longitude != null && library.latitude != null && library.longitude != null) {
                    haversineMiles(latitude, longitude, library.latitude, library.longitude)
                } else {
                    null
                }

                if (distance != null && distance > radiusMiles) {
                    continue
                }

                results += SearchResult(
                    bookId = cursor.getLong(0),
                    title = cursor.getString(1),
                    author = cursor.getString(2) ?: "",
                    isbn = cursor.getString(3) ?: "",
                    publisher = cursor.getString(4) ?: "",
                    publishedYear = cursor.getString(5) ?: "",
                    genre = cursor.getString(6) ?: "",
                    format = cursor.getString(7) ?: "",
                    condition = cursor.getString(8) ?: "",
                    confidence = cursor.getFloat(9),
                    notes = cursor.getString(10) ?: "",
                    library = library,
                    distanceMiles = distance,
                )
            }
        }

        return results.sortedWith(
            compareBy<SearchResult> { it.distanceMiles == null }
                .thenBy { it.distanceMiles ?: Double.MAX_VALUE }
                .thenByDescending { it.confidence }
                .thenBy { it.title.lowercase(Locale.US) }
        )
    }

    fun extractExifLocation(uri: Uri): GeoPoint? {
        return context.contentResolver.openInputStream(uri)?.use { stream ->
            val exif = ExifInterface(stream)
            val latLong = FloatArray(2)
            if (exif.getLatLong(latLong)) {
                GeoPoint(
                    latitude = latLong[0].toDouble(),
                    longitude = latLong[1].toDouble(),
                    source = "photo_exif",
                    confidence = 0.99f,
                )
            } else {
                null
            }
        }
    }

    fun createCameraUri(): Uri {
        val captureDirectory = File(context.cacheDir, "captures").apply { mkdirs() }
        val file = File(captureDirectory, "capture-${System.currentTimeMillis()}.jpg")
        return FileProvider.getUriForFile(
            context,
            "${BuildConfig.APPLICATION_ID}.fileprovider",
            file,
        )
    }

    fun importDemoShelf(): Long {
        val libraries = getLibraries()
        libraries.firstOrNull { it.name == "Blue Little Library" }?.let { return it.id }

        val json = context.resources.openRawResource(R.raw.demo_blue_library).bufferedReader().use { it.readText() }
        val payload = JSONObject(json)
        val books = mutableListOf<BookDraft>()
        payload.getJSONArray("books").forEachObject { item ->
            books += BookDraft(
                title = item.optString("title"),
                author = item.optString("author"),
                isbn = item.optString("isbn"),
                publisher = item.optString("publisher"),
                publishedYear = item.optString("published_year"),
                genre = item.optString("genre"),
                format = item.optString("format"),
                condition = item.optString("condition"),
                confidence = item.optDouble("confidence", 0.5).toFloat(),
                notes = item.optString("notes"),
            )
        }

        return saveLibrary(
            LibraryDraft(
                name = payload.optString("library_name"),
                description = payload.optString("library_description"),
                placeClues = payload.optJSONArray("place_clues")?.joinAsCsv().orEmpty(),
                latitude = payload.optDouble("demo_latitude", 39.539363888888886).toString(),
                longitude = payload.optDouble("demo_longitude", -76.08665277777777).toString(),
                locationSource = "sample_seed",
                locationConfidence = 0.92f,
                books = books,
            )
        )
    }

    private fun copyPhotoToPrivateStore(uri: Uri): String {
        val outputDirectory = File(context.filesDir, "library_photos").apply { mkdirs() }
        val extension = guessExtension(uri)
        val destination = File(outputDirectory, "shelf-${System.currentTimeMillis()}.$extension")
        context.contentResolver.openInputStream(uri)?.use { input ->
            FileOutputStream(destination).use { output ->
                input.copyTo(output)
            }
        }
        return destination.absolutePath
    }

    private fun guessExtension(uri: Uri): String {
        val fallback = "jpg"
        if (uri.scheme == "file") {
            return uri.lastPathSegment?.substringAfterLast('.', fallback)?.lowercase(Locale.US) ?: fallback
        }

        val cursor = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
        val name = cursor?.use {
            if (it.moveToFirst()) {
                it.getString(0)
            } else {
                null
            }
        }
        return name?.substringAfterLast('.', fallback)?.lowercase(Locale.US) ?: fallback
    }

    private fun normalizeText(value: String): String {
        return value.lowercase(Locale.US)
            .replace(Regex("[^a-z0-9\\s-]+"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
    }

    private fun haversineMiles(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val radiusMiles = 3958.7613
        val phi1 = Math.toRadians(lat1)
        val phi2 = Math.toRadians(lat2)
        val deltaPhi = Math.toRadians(lat2 - lat1)
        val deltaLambda = Math.toRadians(lon2 - lon1)

        val a = sin(deltaPhi / 2) * sin(deltaPhi / 2) +
            cos(phi1) * cos(phi2) * sin(deltaLambda / 2) * sin(deltaLambda / 2)
        val c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return radiusMiles * c
    }

    private fun JSONArray.joinAsCsv(): String {
        return buildList {
            for (index in 0 until length()) {
                add(optString(index))
            }
        }.filter { it.isNotBlank() }
            .joinToString(", ")
    }

    private inline fun JSONArray.forEachObject(block: (JSONObject) -> Unit) {
        for (index in 0 until length()) {
            block(getJSONObject(index))
        }
    }

    private fun android.database.Cursor.getNullableDouble(index: Int): Double? {
        return if (isNull(index)) null else getDouble(index)
    }

    private fun ContentValues.putNullableDouble(key: String, value: Double?) {
        if (value == null) {
            putNull(key)
        } else {
            put(key, value)
        }
    }
}
