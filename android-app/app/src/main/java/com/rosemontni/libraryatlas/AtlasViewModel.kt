package com.rosemontni.libraryatlas

import android.app.Application
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class AtlasViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = AtlasRepository(application)

    var selectedTab by mutableIntStateOf(0)
    var stats by mutableStateOf(CatalogStats())
        private set
    var libraries by mutableStateOf<List<LibrarySummary>>(emptyList())
        private set
    var draft by mutableStateOf(LibraryDraft())
        private set
    var searchQuery by mutableStateOf("")
    var searchLatitude by mutableStateOf("")
    var searchLongitude by mutableStateOf("")
    var searchRadiusMiles by mutableStateOf("25")
    var searchResults by mutableStateOf<List<SearchResult>>(emptyList())
        private set
    var centralServerUrl by mutableStateOf(repository.getCentralServerUrl())
        private set
    var statusMessage by mutableStateOf("Pick a photo, review the books, and sync the shelf to the central website.")
        private set
    var busy by mutableStateOf(false)
        private set

    init {
        refreshCatalog()
        if (draft.books.isEmpty()) {
            draft = draft.copy(books = listOf(BookDraft()))
        }
    }

    fun createCameraUri(): Uri = repository.createCameraUri()

    fun onPhotoSelected(uri: Uri) {
        busy = true
        statusMessage = "Reading photo metadata..."
        draft = draft.copy(photoUri = uri.toString())
        viewModelScope.launch(Dispatchers.IO) {
            val location = repository.extractExifLocation(uri)
            withContext(Dispatchers.Main) {
                busy = false
                if (location != null) {
                    draft = draft.copy(
                        latitude = location.latitude?.toString().orEmpty(),
                        longitude = location.longitude?.toString().orEmpty(),
                        locationSource = location.source,
                        locationConfidence = location.confidence,
                    )
                    statusMessage = "EXIF GPS found. Review the shelf details and save when ready."
                } else {
                    draft = draft.copy(locationSource = "manual")
                    statusMessage = "No EXIF GPS found in this photo. You can add location manually or use device location."
                }
            }
        }
    }

    fun useGeoPointForDraft(point: GeoPoint) {
        draft = draft.copy(
            latitude = point.latitude?.toString().orEmpty(),
            longitude = point.longitude?.toString().orEmpty(),
            locationSource = point.source,
            locationConfidence = point.confidence,
        )
        statusMessage = "Location updated from the device."
    }

    fun useGeoPointForSearch(point: GeoPoint) {
        searchLatitude = point.latitude?.toString().orEmpty()
        searchLongitude = point.longitude?.toString().orEmpty()
        statusMessage = "Search origin updated from the device."
    }

    fun updateDraft(
        name: String = draft.name,
        description: String = draft.description,
        placeClues: String = draft.placeClues,
        latitude: String = draft.latitude,
        longitude: String = draft.longitude,
        locationSource: String = draft.locationSource,
        locationConfidence: Float = draft.locationConfidence,
    ) {
        draft = draft.copy(
            name = name,
            description = description,
            placeClues = placeClues,
            latitude = latitude,
            longitude = longitude,
            locationSource = locationSource,
            locationConfidence = locationConfidence,
        )
    }

    fun updateCentralServerUrl(value: String) {
        centralServerUrl = value
        repository.saveCentralServerUrl(value)
    }

    fun addBook() {
        draft = draft.copy(books = draft.books + BookDraft())
    }

    fun removeBook(localId: Long) {
        val nextBooks = draft.books.filterNot { it.localId == localId }
        draft = draft.copy(books = if (nextBooks.isEmpty()) listOf(BookDraft()) else nextBooks)
    }

    fun updateBook(localId: Long, transform: (BookDraft) -> BookDraft) {
        draft = draft.copy(
            books = draft.books.map { book ->
                if (book.localId == localId) transform(book) else book
            }
        )
    }

    fun saveDraft() {
        val draftToSave = draft
        val serverUrl = centralServerUrl.trim()
        busy = true
        statusMessage = if (serverUrl.isBlank()) {
            "Saving library to the on-device atlas..."
        } else {
            "Saving locally and syncing to the central website..."
        }
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val localId = repository.saveLibrary(draftToSave)
                val syncMessage = if (serverUrl.isBlank()) {
                    "Add a central website URL to sync future shelves."
                } else {
                    runCatching {
                        repository.uploadContribution(serverUrl, draftToSave)
                    }.fold(
                        onSuccess = { result ->
                            val countText = if (result.libraries != null && result.books != null) {
                                " The website now has ${result.libraries} shelves and ${result.books} books."
                            } else {
                                ""
                            }
                            "Synced to the central website as library #${result.libraryId}.$countText"
                        },
                        onFailure = { error ->
                            "Saved locally, but central sync failed: ${error.message ?: "unknown error"}"
                        }
                    )
                }
                SaveOutcome(localId, syncMessage)
            }.onSuccess { outcome ->
                withContext(Dispatchers.Main) {
                    refreshCatalog()
                    draft = LibraryDraft(books = listOf(BookDraft()))
                    selectedTab = 1
                    busy = false
                    statusMessage = "Library #${outcome.localId} saved locally. ${outcome.syncMessage}"
                }
            }.onFailure { error ->
                withContext(Dispatchers.Main) {
                    busy = false
                    statusMessage = error.message ?: "Could not save the library."
                }
            }
        }
    }

    fun runSearch() {
        val query = searchQuery.trim()
        if (query.isEmpty()) {
            statusMessage = "Enter a title, author, or ISBN to search."
            return
        }

        busy = true
        statusMessage = "Searching nearby shelves..."
        viewModelScope.launch(Dispatchers.IO) {
            val latitude = searchLatitude.toDoubleOrNull()
            val longitude = searchLongitude.toDoubleOrNull()
            val radius = searchRadiusMiles.toDoubleOrNull() ?: 25.0
            val results = repository.searchBooks(query, latitude, longitude, radius)
            withContext(Dispatchers.Main) {
                searchResults = results
                busy = false
                statusMessage = if (results.isEmpty()) {
                    "No nearby matches yet. Try a different title or widen the radius."
                } else {
                    "Found ${results.size} matching shelf item${if (results.size == 1) "" else "s"}."
                }
            }
        }
    }

    fun importDemoShelf() {
        busy = true
        statusMessage = "Importing the demo shelf..."
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                repository.importDemoShelf()
            }.onSuccess {
                withContext(Dispatchers.Main) {
                    refreshCatalog()
                    selectedTab = 1
                    busy = false
                    statusMessage = "Demo shelf imported. The app is ready to browse."
                }
            }.onFailure { error ->
                withContext(Dispatchers.Main) {
                    busy = false
                    statusMessage = error.message ?: "Could not import the demo shelf."
                }
            }
        }
    }

    private fun refreshCatalog() {
        stats = repository.getStats()
        libraries = repository.getLibraries()
    }

    private data class SaveOutcome(
        val localId: Long,
        val syncMessage: String,
    )
}
