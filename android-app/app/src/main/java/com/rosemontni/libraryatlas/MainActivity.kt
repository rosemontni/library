package com.rosemontni.libraryatlas

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.CameraAlt
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.LibraryBooks
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material.icons.rounded.MyLocation
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.location.LocationManagerCompat
import androidx.core.os.CancellationSignal
import coil.compose.AsyncImage
import java.io.File
import java.util.Locale

private enum class LocationTarget {
    Draft,
    Search,
}

class MainActivity : ComponentActivity() {
    private val viewModel: AtlasViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            LibraryAtlasTheme {
                AtlasApp(viewModel)
            }
        }
    }
}

@Composable
private fun AtlasApp(viewModel: AtlasViewModel) {
    val context = LocalContext.current
    var pendingLocationTarget by remember { mutableStateOf(LocationTarget.Draft) }
    var cameraUri by remember { mutableStateOf<Uri?>(null) }

    val pickPhotoLauncher = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) {
            viewModel.onPhotoSelected(uri)
        }
    }

    val takePhotoLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        if (success) {
            cameraUri?.let(viewModel::onPhotoSelected)
        }
    }

    val locationPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            requestCurrentLocation(context) { geoPoint ->
                if (geoPoint == null) {
                    viewModel.updateDraft(locationSource = "manual")
                } else {
                    if (pendingLocationTarget == LocationTarget.Draft) {
                        viewModel.useGeoPointForDraft(geoPoint)
                    } else {
                        viewModel.useGeoPointForSearch(geoPoint)
                    }
                }
            }
        } else {
            viewModel.updateDraft(locationSource = viewModel.draft.locationSource)
        }
    }

    val screenTitles = listOf("Capture", "Atlas", "Search")

    Scaffold(
        containerColor = Color(0xFFF3EEE6),
        topBar = {
            Surface(shadowElevation = 8.dp) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(
                            Brush.verticalGradient(
                                listOf(Color(0xFF123241), Color(0xFF1E4D5A))
                            )
                        )
                        .padding(horizontal = 20.dp, vertical = 18.dp)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            text = "Little Library Atlas",
                            color = Color(0xFFF9F6F0),
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = viewModel.statusMessage,
                            color = Color(0xFFDBE9E3),
                            style = MaterialTheme.typography.bodyMedium,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                        StatsRow(viewModel.stats)
                    }
                }
            }
        },
        bottomBar = {
            NavigationBar(containerColor = Color(0xFFF9F5EE)) {
                val icons = listOf(Icons.Rounded.CameraAlt, Icons.Rounded.LibraryBooks, Icons.Rounded.Search)
                screenTitles.forEachIndexed { index, title ->
                    NavigationBarItem(
                        selected = viewModel.selectedTab == index,
                        onClick = { viewModel.selectedTab = index },
                        icon = { Icon(icons[index], contentDescription = title) },
                        label = { Text(title) },
                    )
                }
            }
        }
    ) { padding ->
        when (viewModel.selectedTab) {
            0 -> CaptureScreen(
                modifier = Modifier.padding(padding),
                viewModel = viewModel,
                onPickPhoto = {
                    pickPhotoLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                },
                onTakePhoto = {
                    val nextCameraUri = viewModel.createCameraUri()
                    cameraUri = nextCameraUri
                    takePhotoLauncher.launch(nextCameraUri)
                },
                onUseCurrentLocation = {
                    pendingLocationTarget = LocationTarget.Draft
                    ensureLocationPermission(context, locationPermissionLauncher) {
                        requestCurrentLocation(context) { geoPoint ->
                            geoPoint?.let(viewModel::useGeoPointForDraft)
                        }
                    }
                },
            )

            1 -> AtlasScreen(
                modifier = Modifier.padding(padding),
                viewModel = viewModel,
            )

            else -> SearchScreen(
                modifier = Modifier.padding(padding),
                viewModel = viewModel,
                onUseCurrentLocation = {
                    pendingLocationTarget = LocationTarget.Search
                    ensureLocationPermission(context, locationPermissionLauncher) {
                        requestCurrentLocation(context) { geoPoint ->
                            geoPoint?.let(viewModel::useGeoPointForSearch)
                        }
                    }
                }
            )
        }
    }
}

@Composable
private fun StatsRow(stats: CatalogStats) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        SummaryPill(label = "Libraries", value = stats.libraries.toString())
        SummaryPill(label = "Books", value = stats.books.toString())
        SummaryPill(label = "Mode", value = "Central sync")
    }
}

@Composable
private fun SummaryPill(label: String, value: String) {
    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(containerColor = Color(0x20F7F2E8)),
        shape = RoundedCornerShape(18.dp)
    ) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            Text(label, color = Color(0xFFCAE0D8), fontSize = 12.sp)
            Text(value, color = Color(0xFFF8F4EC), fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun CaptureScreen(
    modifier: Modifier,
    viewModel: AtlasViewModel,
    onPickPhoto: () -> Unit,
    onTakePhoto: () -> Unit,
    onUseCurrentLocation: () -> Unit,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Card(
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFFF9F5EE))
            ) {
                Column(
                    modifier = Modifier.padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Text("Shelf intake", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text(
                        "Import a shelf photo, keep the EXIF geotag when it exists, then sync the reviewed catalog to the website database.",
                        color = Color(0xFF55646D)
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedButton(onClick = onPickPhoto) {
                            Icon(Icons.Rounded.PhotoLibrary, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text("Pick photo")
                        }
                        Button(onClick = onTakePhoto) {
                            Icon(Icons.Rounded.CameraAlt, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text("Take photo")
                        }
                    }
                    OutlinedButton(onClick = onUseCurrentLocation) {
                        Icon(Icons.Rounded.MyLocation, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Use device location")
                    }
                    OutlinedTextField(
                        value = viewModel.centralServerUrl,
                        onValueChange = { viewModel.updateCentralServerUrl(it) },
                        label = { Text("Central website URL") },
                        placeholder = { Text("https://your-library-site.example") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                    )
                    Text(
                        "When a URL is set, Save keeps a phone copy and contributes this shelf to the central website.",
                        color = Color(0xFF55646D)
                    )
                }
            }
        }

        item {
            PhotoPreviewCard(viewModel.draft.photoUri)
        }

        item {
            DraftFields(viewModel)
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Books on shelf", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                IconButton(onClick = { viewModel.addBook() }) {
                    Icon(Icons.Rounded.Add, contentDescription = "Add book")
                }
            }
        }

        items(viewModel.draft.books, key = { it.localId }) { book ->
            BookEditorCard(
                book = book,
                onRemove = { viewModel.removeBook(book.localId) },
                onUpdate = { transform -> viewModel.updateBook(book.localId, transform) },
            )
        }

        item {
            Button(
                onClick = { viewModel.saveDraft() },
                modifier = Modifier.fillMaxWidth(),
                enabled = !viewModel.busy,
            ) {
                Icon(Icons.Rounded.LibraryBooks, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (viewModel.centralServerUrl.isBlank()) "Save local draft" else "Save + sync to website")
            }
        }
    }
}

@Composable
private fun PhotoPreviewCard(photoUri: String) {
    ElevatedCard(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFFEEF3F1))
    ) {
        if (photoUri.isBlank()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(220.dp)
                    .padding(18.dp),
                contentAlignment = Alignment.Center
            ) {
                Text("The selected shelf photo will appear here.")
            }
        } else {
            AsyncImage(
                model = Uri.parse(photoUri),
                contentDescription = "Selected library photo",
                modifier = Modifier
                    .fillMaxWidth()
                    .height(260.dp)
                    .clip(RoundedCornerShape(24.dp)),
                contentScale = ContentScale.Crop
            )
        }
    }
}

@Composable
private fun DraftFields(viewModel: AtlasViewModel) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF9F5EE))
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            OutlinedTextField(
                value = viewModel.draft.name,
                onValueChange = { viewModel.updateDraft(name = it) },
                label = { Text("Library name") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = viewModel.draft.description,
                onValueChange = { viewModel.updateDraft(description = it) },
                label = { Text("Description") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2
            )
            OutlinedTextField(
                value = viewModel.draft.placeClues,
                onValueChange = { viewModel.updateDraft(placeClues = it) },
                label = { Text("Place clues") },
                modifier = Modifier.fillMaxWidth()
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = viewModel.draft.latitude,
                    onValueChange = { viewModel.updateDraft(latitude = it) },
                    label = { Text("Latitude") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = viewModel.draft.longitude,
                    onValueChange = { viewModel.updateDraft(longitude = it) },
                    label = { Text("Longitude") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.weight(1f)
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = viewModel.draft.locationSource,
                    onValueChange = { viewModel.updateDraft(locationSource = it) },
                    label = { Text("Location source") },
                    modifier = Modifier.weight(1f)
                )
                Column(modifier = Modifier.weight(1f)) {
                    Text("Location confidence", color = Color(0xFF55646D))
                    Slider(
                        value = viewModel.draft.locationConfidence,
                        onValueChange = { viewModel.updateDraft(locationConfidence = it) },
                        valueRange = 0f..1f
                    )
                    Text(String.format(Locale.US, "%.2f", viewModel.draft.locationConfidence))
                }
            }
        }
    }
}

@Composable
private fun BookEditorCard(
    book: BookDraft,
    onRemove: () -> Unit,
    onUpdate: (((BookDraft) -> BookDraft)) -> Unit,
) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF9F5EE))
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Book entry", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                IconButton(onClick = onRemove) {
                    Icon(Icons.Rounded.Delete, contentDescription = "Delete book")
                }
            }
            OutlinedTextField(
                value = book.title,
                onValueChange = { value -> onUpdate { it.copy(title = value) } },
                label = { Text("Title") },
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = book.author,
                onValueChange = { value -> onUpdate { it.copy(author = value) } },
                label = { Text("Author") },
                modifier = Modifier.fillMaxWidth()
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = book.isbn,
                    onValueChange = { value -> onUpdate { it.copy(isbn = value) } },
                    label = { Text("ISBN") },
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = book.genre,
                    onValueChange = { value -> onUpdate { it.copy(genre = value) } },
                    label = { Text("Genre") },
                    modifier = Modifier.weight(1f)
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = book.format,
                    onValueChange = { value -> onUpdate { it.copy(format = value) } },
                    label = { Text("Format") },
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = book.condition,
                    onValueChange = { value -> onUpdate { it.copy(condition = value) } },
                    label = { Text("Condition") },
                    modifier = Modifier.weight(1f)
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = book.publisher,
                    onValueChange = { value -> onUpdate { it.copy(publisher = value) } },
                    label = { Text("Publisher") },
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = book.publishedYear,
                    onValueChange = { value -> onUpdate { it.copy(publishedYear = value) } },
                    label = { Text("Year") },
                    modifier = Modifier.weight(1f)
                )
            }
            Column {
                Text("Confidence", color = Color(0xFF55646D))
                Slider(
                    value = book.confidence,
                    onValueChange = { value -> onUpdate { it.copy(confidence = value) } },
                    valueRange = 0f..1f
                )
                Text(String.format(Locale.US, "%.2f", book.confidence))
            }
            OutlinedTextField(
                value = book.notes,
                onValueChange = { value -> onUpdate { it.copy(notes = value) } },
                label = { Text("Notes") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2
            )
        }
    }
}

@Composable
private fun AtlasScreen(
    modifier: Modifier,
    viewModel: AtlasViewModel,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Card(
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFFF9F5EE))
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Phone copy", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                        Text("Saved shelves stay searchable here; the configured website keeps the central database.")
                    }
                    OutlinedButton(onClick = { viewModel.importDemoShelf() }, enabled = !viewModel.busy) {
                        Icon(Icons.Rounded.AutoAwesome, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Import demo shelf")
                    }
                }
            }
        }

        if (viewModel.libraries.isEmpty()) {
            item {
                EmptyAtlasCard()
            }
        } else {
            items(viewModel.libraries, key = { it.id }) { library ->
                LibrarySummaryCard(library)
            }
        }
    }
}

@Composable
private fun EmptyAtlasCard() {
    ElevatedCard(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFFEEF3F1))
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text("No shelves saved yet.", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("Capture one from the first tab or import the demo shelf to make the app immediately explorable.")
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun LibrarySummaryCard(library: LibrarySummary) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF9F5EE))
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            if (!library.photoPath.isNullOrBlank()) {
                AsyncImage(
                    model = File(library.photoPath),
                    contentDescription = library.name,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(170.dp)
                        .clip(RoundedCornerShape(18.dp)),
                    contentScale = ContentScale.Crop
                )
            }

            Text(library.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(library.description.ifBlank { "No description saved." }, color = Color(0xFF55646D))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = true, onClick = {}, label = { Text("${library.bookCount} items") })
                FilterChip(selected = true, onClick = {}, label = { Text(library.locationSource) })
                if (library.latitude != null && library.longitude != null) {
                    FilterChip(
                        selected = true,
                        onClick = {},
                        label = {
                            Text(
                                String.format(
                                    Locale.US,
                                    "%.4f, %.4f",
                                    library.latitude,
                                    library.longitude
                                )
                            )
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun SearchScreen(
    modifier: Modifier,
    viewModel: AtlasViewModel,
    onUseCurrentLocation: () -> Unit,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Card(
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFFF9F5EE))
            ) {
                Column(
                    modifier = Modifier.padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("Find nearby copies", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    OutlinedTextField(
                        value = viewModel.searchQuery,
                        onValueChange = { viewModel.searchQuery = it },
                        label = { Text("Title, author, or ISBN") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedTextField(
                            value = viewModel.searchLatitude,
                            onValueChange = { viewModel.searchLatitude = it },
                            label = { Text("Latitude") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            modifier = Modifier.weight(1f)
                        )
                        OutlinedTextField(
                            value = viewModel.searchLongitude,
                            onValueChange = { viewModel.searchLongitude = it },
                            label = { Text("Longitude") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            modifier = Modifier.weight(1f)
                        )
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = viewModel.searchRadiusMiles,
                            onValueChange = { viewModel.searchRadiusMiles = it },
                            label = { Text("Radius miles") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            modifier = Modifier.weight(1f)
                        )
                        OutlinedButton(onClick = onUseCurrentLocation) {
                            Icon(Icons.Rounded.MyLocation, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text("Use device")
                        }
                    }
                    Button(onClick = { viewModel.runSearch() }, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Rounded.Search, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Search shelves")
                    }
                }
            }
        }

        if (viewModel.searchResults.isEmpty()) {
            item {
                ElevatedCard(
                    shape = RoundedCornerShape(24.dp),
                    colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFFEEF3F1))
                ) {
                    Text(
                        text = "Search results will appear here with the closest matching shelf first.",
                        modifier = Modifier.padding(20.dp)
                    )
                }
            }
        } else {
            items(viewModel.searchResults, key = { it.bookId }) { result ->
                SearchResultCard(result)
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SearchResultCard(result: SearchResult) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF9F5EE))
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(result.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(result.author.ifBlank { "Unknown author" }, color = Color(0xFF55646D))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (result.genre.isNotBlank()) {
                    FilterChip(selected = true, onClick = {}, label = { Text(result.genre) })
                }
                if (result.format.isNotBlank()) {
                    FilterChip(selected = true, onClick = {}, label = { Text(result.format) })
                }
                if (result.condition.isNotBlank()) {
                    FilterChip(selected = true, onClick = {}, label = { Text(result.condition) })
                }
                FilterChip(
                    selected = true,
                    onClick = {},
                    label = { Text(result.distanceMiles?.let { String.format(Locale.US, "%.1f mi", it) } ?: "Distance unavailable") }
                )
            }
            Text(result.library.name, fontWeight = FontWeight.SemiBold)
            Text(result.library.description.ifBlank { "No library description saved." }, color = Color(0xFF55646D))
            if (result.library.latitude != null && result.library.longitude != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Rounded.Map, contentDescription = null, tint = Color(0xFF2C625E))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        String.format(
                            Locale.US,
                            "%.4f, %.4f",
                            result.library.latitude,
                            result.library.longitude
                        )
                    )
                }
            }
        }
    }
}

private fun ensureLocationPermission(
    context: Context,
    launcher: androidx.activity.result.ActivityResultLauncher<String>,
    onGranted: () -> Unit,
) {
    if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
        onGranted()
    } else {
        launcher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
    }
}

@SuppressLint("MissingPermission")
private fun requestCurrentLocation(context: Context, onResult: (GeoPoint?) -> Unit) {
    val locationManager = context.getSystemService(LocationManager::class.java) ?: run {
        onResult(null)
        return
    }

    val cancellationSignal = CancellationSignal()
    val executor = ContextCompat.getMainExecutor(context)

    fun request(provider: String, fallback: (() -> Unit)? = null) {
        LocationManagerCompat.getCurrentLocation(locationManager, provider, cancellationSignal, executor) { location ->
            if (location != null) {
                onResult(
                    GeoPoint(
                        latitude = location.latitude,
                        longitude = location.longitude,
                        source = "device_location",
                        confidence = if (location.accuracy <= 20f) 0.97f else 0.9f,
                        accuracyMeters = location.accuracy,
                    )
                )
            } else {
                fallback?.invoke() ?: onResult(null)
            }
        }
    }

    request(LocationManager.GPS_PROVIDER) {
        request(LocationManager.NETWORK_PROVIDER)
    }
}

@Composable
private fun LibraryAtlasTheme(content: @Composable () -> Unit) {
    val colorScheme = lightColorScheme(
        primary = Color(0xFF1E5A61),
        onPrimary = Color(0xFFF7F3EC),
        primaryContainer = Color(0xFFCFE0DD),
        secondary = Color(0xFFC56D4A),
        tertiary = Color(0xFFD3AC59),
        background = Color(0xFFF3EEE6),
        surface = Color(0xFFF9F5EE),
        onSurface = Color(0xFF19262E),
    )

    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
