package com.rosemontni.libraryatlas

data class GeoPoint(
    val latitude: Double? = null,
    val longitude: Double? = null,
    val source: String = "manual",
    val confidence: Float = 0f,
    val accuracyMeters: Float? = null,
)

data class BookDraft(
    val localId: Long = System.nanoTime(),
    val title: String = "",
    val author: String = "",
    val isbn: String = "",
    val publisher: String = "",
    val publishedYear: String = "",
    val genre: String = "",
    val format: String = "",
    val condition: String = "",
    val confidence: Float = 0.5f,
    val notes: String = "",
)

data class LibraryDraft(
    val photoUri: String = "",
    val name: String = "",
    val description: String = "",
    val placeClues: String = "",
    val latitude: String = "",
    val longitude: String = "",
    val locationSource: String = "manual",
    val locationConfidence: Float = 0f,
    val books: List<BookDraft> = listOf(BookDraft()),
)

data class CatalogStats(
    val libraries: Int = 0,
    val books: Int = 0,
)

data class CentralUploadResult(
    val libraryId: Long,
    val libraries: Int? = null,
    val books: Int? = null,
)

data class LibrarySummary(
    val id: Long,
    val name: String,
    val description: String,
    val latitude: Double?,
    val longitude: Double?,
    val photoPath: String?,
    val locationSource: String,
    val locationConfidence: Float,
    val bookCount: Int,
)

data class SearchResult(
    val bookId: Long,
    val title: String,
    val author: String,
    val isbn: String,
    val publisher: String,
    val publishedYear: String,
    val genre: String,
    val format: String,
    val condition: String,
    val confidence: Float,
    val notes: String,
    val library: LibrarySummary,
    val distanceMiles: Double?,
)
