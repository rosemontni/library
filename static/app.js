const state = {
  captureLocation: null,
  searchLocation: null,
  currentDraft: null,
  activeCategory: "",
  libraries: [],
  map: null,
  markers: new Map(),
  markerBounds: null,
};

const elements = {
  libraryCount: document.getElementById("libraryCount"),
  bookCount: document.getElementById("bookCount"),
  modelName: document.getElementById("modelName"),
  atlasMap: document.getElementById("atlasMap"),
  mapStatus: document.getElementById("mapStatus"),
  fitMapButton: document.getElementById("fitMapButton"),
  mapLibraryList: document.getElementById("mapLibraryList"),
  captureForm: document.getElementById("captureForm"),
  booksPhotoInput: document.getElementById("booksPhotoInput"),
  locationPhotoInput: document.getElementById("locationPhotoInput"),
  booksPhotoPreview: document.getElementById("booksPhotoPreview"),
  booksPreviewPlaceholder: document.getElementById("booksPreviewPlaceholder"),
  locationPhotoPreview: document.getElementById("locationPhotoPreview"),
  locationPreviewPlaceholder: document.getElementById("locationPreviewPlaceholder"),
  useCaptureLocation: document.getElementById("useCaptureLocation"),
  captureLocationStatus: document.getElementById("captureLocationStatus"),
  analysisStatus: document.getElementById("analysisStatus"),
  libraryDraftForm: document.getElementById("libraryDraftForm"),
  libraryName: document.getElementById("libraryName"),
  locationSource: document.getElementById("locationSource"),
  latitude: document.getElementById("latitude"),
  longitude: document.getElementById("longitude"),
  locationConfidence: document.getElementById("locationConfidence"),
  accuracyMeters: document.getElementById("accuracyMeters"),
  libraryDescription: document.getElementById("libraryDescription"),
  photoSummary: document.getElementById("photoSummary"),
  placeClues: document.getElementById("placeClues"),
  booksTableBody: document.getElementById("booksTableBody"),
  addBookRow: document.getElementById("addBookRow"),
  searchForm: document.getElementById("searchForm"),
  searchQuery: document.getElementById("searchQuery"),
  searchZipCode: document.getElementById("searchZipCode"),
  searchRadius: document.getElementById("searchRadius"),
  useSearchLocation: document.getElementById("useSearchLocation"),
  searchLocationStatus: document.getElementById("searchLocationStatus"),
  searchResults: document.getElementById("searchResults"),
  bookRowTemplate: document.getElementById("bookRowTemplate"),
  topicChips: Array.from(document.querySelectorAll(".topic-chip")),
};

const LOCAL_ZIP_CENTROIDS = Object.freeze({
  "20001": { latitude: 38.9101, longitude: -77.0171, label: "Washington, DC 20001" },
  "20002": { latitude: 38.9057, longitude: -76.9845, label: "Washington, DC 20002" },
  "20003": { latitude: 38.884, longitude: -76.994, label: "Washington, DC 20003" },
  "20007": { latitude: 38.9146, longitude: -77.0742, label: "Washington, DC 20007" },
  "20740": { latitude: 38.996, longitude: -76.929, label: "College Park, MD 20740" },
  "20814": { latitude: 38.9907, longitude: -77.1003, label: "Bethesda, MD 20814" },
  "20815": { latitude: 38.9834, longitude: -77.0789, label: "Chevy Chase, MD 20815" },
  "20817": { latitude: 39.0007, longitude: -77.1547, label: "Bethesda, MD 20817" },
  "20850": { latitude: 39.0891, longitude: -77.1837, label: "Rockville, MD 20850" },
  "20852": { latitude: 39.0497, longitude: -77.1209, label: "North Bethesda, MD 20852" },
  "20854": { latitude: 39.0384, longitude: -77.2003, label: "Potomac, MD 20854" },
  "20877": { latitude: 39.1434, longitude: -77.2014, label: "Gaithersburg, MD 20877" },
  "20878": { latitude: 39.1148, longitude: -77.2469, label: "Gaithersburg, MD 20878" },
  "20879": { latitude: 39.1699, longitude: -77.1696, label: "Gaithersburg, MD 20879" },
  "20895": { latitude: 39.0297, longitude: -77.0764, label: "Kensington, MD 20895" },
  "20901": { latitude: 39.0219, longitude: -77.0077, label: "Silver Spring, MD 20901" },
  "20902": { latitude: 39.0438, longitude: -77.0458, label: "Silver Spring, MD 20902" },
  "20910": { latitude: 38.9987, longitude: -77.033, label: "Silver Spring, MD 20910" },
  "20912": { latitude: 38.9807, longitude: -76.9897, label: "Takoma Park, MD 20912" },
  "21044": { latitude: 39.207, longitude: -76.883, label: "Columbia, MD 21044" },
  "21201": { latitude: 39.2953, longitude: -76.6181, label: "Baltimore, MD 21201" },
  "22201": { latitude: 38.8865, longitude: -77.095, label: "Arlington, VA 22201" },
  "22202": { latitude: 38.8564, longitude: -77.0539, label: "Arlington, VA 22202" },
  "22203": { latitude: 38.8735, longitude: -77.1175, label: "Arlington, VA 22203" },
  "22204": { latitude: 38.8613, longitude: -77.0985, label: "Arlington, VA 22204" },
  "22205": { latitude: 38.8836, longitude: -77.139, label: "Arlington, VA 22205" },
  "22301": { latitude: 38.8197, longitude: -77.0584, label: "Alexandria, VA 22301" },
});

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "Request failed.");
  }
  return payload;
}

function formatNumber(value, digits = 4) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  return Number(value).toFixed(digits);
}

function setCallout(message, mode = "muted") {
  elements.analysisStatus.className = `callout ${mode}`.trim();
  elements.analysisStatus.textContent = message;
}

function updateCounts(counts) {
  elements.libraryCount.textContent = counts?.libraries ?? 0;
  elements.bookCount.textContent = counts?.books ?? 0;
}

function normalizeZipCode(value) {
  const match = String(value ?? "")
    .trim()
    .match(/^(\d{5})(?:-\d{4})?$/);
  return match ? match[1] : "";
}

async function lookupZipCode(value) {
  const zipCode = normalizeZipCode(value);
  if (!zipCode) {
    throw new Error("Enter a valid 5-digit ZIP code, or leave ZIP blank to search all libraries.");
  }

  if (LOCAL_ZIP_CENTROIDS[zipCode]) {
    return { ...LOCAL_ZIP_CENTROIDS[zipCode], zipCode };
  }

  const response = await fetch(`https://api.zippopotam.us/us/${zipCode}`);
  if (!response.ok) {
    throw new Error(`Could not look up ZIP code ${zipCode}. Try browser location or leave ZIP blank.`);
  }

  const payload = await response.json();
  const place = payload.places?.[0];
  const latitude = Number(place?.latitude);
  const longitude = Number(place?.longitude);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new Error(`Could not read coordinates for ZIP code ${zipCode}.`);
  }

  const label = [place["place name"], place["state abbreviation"], zipCode].filter(Boolean).join(", ");
  return { latitude, longitude, label, zipCode };
}

function libraryHasCoordinates(library) {
  return library.latitude !== null && library.latitude !== undefined && library.longitude !== null && library.longitude !== undefined;
}

function libraryPhoto(library) {
  return library.location_photo_url || library.photo_url || library.books_photo_url || "";
}

function initMap() {
  if (state.map || !elements.atlasMap) {
    return;
  }

  if (!window.L) {
    elements.atlasMap.innerHTML = `<div class="map-loading">Map library unavailable. Check your network connection for OpenStreetMap tiles.</div>`;
    elements.mapStatus.textContent = "The library list still works, but the zoomable map could not load.";
    return;
  }

  elements.atlasMap.innerHTML = "";
  state.map = L.map(elements.atlasMap, {
    zoomControl: true,
    scrollWheelZoom: true,
  }).setView([39.12, -77.15], 10);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(state.map);
}

function markerIcon(bookCount = 0) {
  return L.divIcon({
    className: "atlas-marker",
    html: `<span><b>${bookCount}</b></span>`,
    iconSize: [38, 44],
    iconAnchor: [19, 42],
    popupAnchor: [0, -38],
  });
}

function popupHtml(library) {
  const photo = libraryPhoto(library);
  const sampleBooks = (library.sample_books || [])
    .map((title) => `<li>${escapeHtml(title)}</li>`)
    .join("");
  return `
    <article class="map-popup">
      ${photo ? `<img src="${escapeHtml(photo)}" alt="${escapeHtml(library.name)} locator photo" />` : ""}
      <strong>${escapeHtml(library.name)}</strong>
      <p>${escapeHtml(library.description || "No description saved yet.")}</p>
      <small>${library.book_count || 0} books · ${escapeHtml(library.location_source || "manual")}</small>
      ${sampleBooks ? `<ul>${sampleBooks}</ul>` : ""}
    </article>
  `;
}

function renderMap(libraries) {
  initMap();
  if (!state.map || !window.L) {
    return;
  }

  state.markers.forEach((marker) => marker.remove());
  state.markers.clear();

  const mappedLibraries = libraries.filter(libraryHasCoordinates);
  const markerCoordinates = [];
  mappedLibraries.forEach((library) => {
    const coordinates = [library.latitude, library.longitude];
    const marker = L.marker(coordinates, { icon: markerIcon(library.book_count) })
      .addTo(state.map)
      .bindPopup(popupHtml(library), { maxWidth: 290 });
    state.markers.set(library.id, marker);
    markerCoordinates.push(coordinates);
  });

  if (markerCoordinates.length) {
    state.markerBounds = L.latLngBounds(markerCoordinates);
    state.map.fitBounds(state.markerBounds, { padding: [42, 42], maxZoom: 14 });
    elements.mapStatus.textContent = `${markerCoordinates.length} mapped shelves. Scroll or pinch to zoom.`;
  } else {
    state.markerBounds = null;
    elements.mapStatus.textContent = "No saved libraries have coordinates yet.";
  }
}

function renderLibraryList(libraries) {
  elements.mapLibraryList.innerHTML = "";

  if (!libraries.length) {
    elements.mapLibraryList.innerHTML = `<div class="result-empty">No libraries saved yet. Add one from the contribute panel.</div>`;
    return;
  }

  libraries.forEach((library) => {
    const card = document.createElement("article");
    card.className = "library-mini-card";
    const photo = libraryPhoto(library);
    const coords = libraryHasCoordinates(library)
      ? `${formatNumber(library.latitude)}°, ${formatNumber(library.longitude)}°`
      : "Coordinates missing";
    const samples = (library.sample_books || []).slice(0, 3).map(escapeHtml).join(" · ");
    card.innerHTML = `
      ${photo ? `<img src="${escapeHtml(photo)}" alt="${escapeHtml(library.name)} locator photo" />` : `<div class="library-mini-empty">No photo</div>`}
      <div>
        <h3>${escapeHtml(library.name)}</h3>
        <p>${escapeHtml(library.description || "No description saved yet.")}</p>
        <div class="mini-meta">
          <span>${library.book_count || 0} books</span>
          <span>${escapeHtml(coords)}</span>
        </div>
        ${samples ? `<small>${samples}</small>` : ""}
      </div>
    `;
    if (libraryHasCoordinates(library)) {
      card.tabIndex = 0;
      card.role = "button";
      card.setAttribute("aria-label", `Show ${library.name} on the map`);
      const focusMarker = () => {
        const marker = state.markers.get(library.id);
        if (state.map && marker) {
          state.map.flyTo([library.latitude, library.longitude], Math.max(state.map.getZoom(), 15), { duration: 0.8 });
          marker.openPopup();
        }
      };
      card.addEventListener("click", focusMarker);
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          focusMarker();
        }
      });
    }
    elements.mapLibraryList.appendChild(card);
  });
}

async function loadLibraries() {
  const payload = await fetchJSON("/api/libraries");
  state.libraries = payload.libraries || [];
  renderLibraryList(state.libraries);
  renderMap(state.libraries);
}

function previewSelectedPhoto(file, imageElement, placeholderElement) {
  if (!file) {
    imageElement.hidden = true;
    placeholderElement.hidden = false;
    return;
  }

  const url = URL.createObjectURL(file);
  imageElement.src = url;
  imageElement.hidden = false;
  placeholderElement.hidden = true;
}

async function requestLocation(statusElement) {
  if (!navigator.geolocation) {
    throw new Error("This browser does not support geolocation.");
  }

  statusElement.textContent = "Requesting your location...";

  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const location = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy_meters: position.coords.accuracy,
        };
        resolve(location);
      },
      (error) => {
        reject(new Error(error.message || "Location permission was denied."));
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 10000 }
    );
  });
}

function addBookRow(book = {}) {
  const fragment = elements.bookRowTemplate.content.cloneNode(true);
  const row = fragment.querySelector("tr");

  row.querySelectorAll("[data-field]").forEach((input) => {
    const field = input.dataset.field;
    input.value = book[field] ?? "";
  });

  row.querySelector(".remove-row").addEventListener("click", () => {
    row.remove();
  });

  elements.booksTableBody.appendChild(fragment);
}

function renderBooks(books = []) {
  elements.booksTableBody.innerHTML = "";

  if (!books.length) {
    addBookRow({
      title: "",
      author: "",
      isbn: "",
      genre: "",
      format: "",
      condition: "",
      publisher: "",
      published_year: "",
      confidence: 0.2,
      notes: "",
    });
    return;
  }

  books.forEach((book) => addBookRow(book));
}

function renderDraft(draft) {
  state.currentDraft = draft;
  elements.libraryDraftForm.hidden = false;

  elements.libraryName.value = draft.library_name || "";
  elements.locationSource.value = draft.geolocation?.source || "";
  elements.latitude.value = draft.geolocation?.latitude ?? "";
  elements.longitude.value = draft.geolocation?.longitude ?? "";
  elements.locationConfidence.value = draft.geolocation?.confidence ?? "";
  elements.accuracyMeters.value = draft.geolocation?.accuracy_meters ?? "";
  elements.libraryDescription.value = draft.library_description || "";
  elements.photoSummary.value = draft.photo_summary || "";
  elements.placeClues.value = (draft.place_clues || []).join(", ");

  renderBooks(draft.books || []);

  if (draft.warnings?.length) {
    setCallout(draft.warnings.join(" "), "error");
  } else {
    setCallout("Draft ready. Review the location and book rows, then save this library into the atlas.", "muted");
  }
}

function collectBooks() {
  return Array.from(elements.booksTableBody.querySelectorAll("tr"))
    .map((row) => {
      const record = {};
      row.querySelectorAll("[data-field]").forEach((input) => {
        record[input.dataset.field] = input.value.trim();
      });
      record.confidence = Number(record.confidence || 0);
      return record;
    })
    .filter((book) => book.title);
}

function collectDraftPayload() {
  return {
    library_name: elements.libraryName.value.trim(),
    library_description: elements.libraryDescription.value.trim(),
    photo_path: state.currentDraft?.photo_url?.replace(/^\//, "") || "",
    books_photo_path: state.currentDraft?.books_photo_url?.replace(/^\//, "") || "",
    location_photo_path: state.currentDraft?.location_photo_url?.replace(/^\//, "") || "",
    place_clues: elements.placeClues.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    geolocation: {
      latitude: elements.latitude.value ? Number(elements.latitude.value) : null,
      longitude: elements.longitude.value ? Number(elements.longitude.value) : null,
      source: elements.locationSource.value.trim() || "manual",
      confidence: elements.locationConfidence.value ? Number(elements.locationConfidence.value) : 0,
      accuracy_meters: elements.accuracyMeters.value ? Number(elements.accuracyMeters.value) : null,
    },
    books: collectBooks(),
  };
}

function formatDistance(value) {
  if (value === null || value === undefined) {
    return "Distance unavailable";
  }
  return `${value.toFixed(1)} mi away`;
}

function setActiveCategory(category) {
  state.activeCategory = state.activeCategory === category ? "" : category;
  elements.topicChips.forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.category === state.activeCategory);
    chip.setAttribute("aria-pressed", String(chip.dataset.category === state.activeCategory));
  });
}

function renderSearchResults(results) {
  elements.searchResults.innerHTML = "";

  if (!results.length) {
    elements.searchResults.innerHTML = `<div class="result-empty">No matching books were found within the selected radius yet. Try a broader category or a wider radius.</div>`;
    return;
  }

  const groups = new Map();
  results.forEach((result) => {
    const key = result.library.id;
    if (!groups.has(key)) {
      groups.set(key, {
        library: result.library,
        distance_miles: result.distance_miles,
        books: [],
      });
    }
    groups.get(key).books.push(result);
  });

  Array.from(groups.values()).forEach((group) => {
    const article = document.createElement("article");
    article.className = "result-card";

    const distanceLabel = formatDistance(group.distance_miles);
    const libraryCoords =
      group.library.latitude !== null && group.library.longitude !== null
        ? `${formatNumber(group.library.latitude)}°, ${formatNumber(group.library.longitude)}°`
        : "Coordinates not saved";

    const locatorPhoto = group.library.location_photo_url || group.library.photo_url;
    const matchedBooks = group.books
      .map((book) => {
        const details = [book.author, book.genre, book.format].filter(Boolean).map(escapeHtml).join(" · ");
        return `
          <li>
            <strong>${escapeHtml(book.title)}</strong>
            ${details ? `<span>${details}</span>` : ""}
          </li>
        `;
      })
      .join("");

    article.innerHTML = `
      ${
        locatorPhoto
          ? `<img class="result-photo" src="${escapeHtml(locatorPhoto)}" alt="${escapeHtml(group.library.name)} locator photo" />`
          : `<div class="result-photo result-photo-empty">No locator photo</div>`
      }
      <div class="result-head">
        <div>
          <h3 class="result-title">${escapeHtml(group.library.name)}</h3>
          <p>${escapeHtml(group.library.description || "No library description saved yet.")}</p>
        </div>
        <span class="distance-pill">${escapeHtml(distanceLabel)}</span>
      </div>
      <div class="result-meta compact-meta">
        <span>${group.books.length} matching book${group.books.length === 1 ? "" : "s"}</span>
        <span>${escapeHtml(libraryCoords)}</span>
        <span>${escapeHtml(group.library.location_source || "manual")}</span>
      </div>
      <ul class="matched-books">${matchedBooks}</ul>
    `;

    if (group.library?.id && libraryHasCoordinates(group.library)) {
      article.tabIndex = 0;
      article.role = "button";
      article.setAttribute("aria-label", `Show ${group.library.name} on the map`);
      const focusMarker = () => {
        const marker = state.markers.get(group.library.id);
        if (state.map && marker) {
          state.map.flyTo([group.library.latitude, group.library.longitude], Math.max(state.map.getZoom(), 15), { duration: 0.8 });
          marker.openPopup();
        }
      };
      article.addEventListener("click", focusMarker);
      article.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          focusMarker();
        }
      });
    }

    elements.searchResults.appendChild(article);
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function loadConfig() {
  const payload = await fetchJSON("/api/config");
  updateCounts(payload.counts);
  elements.modelName.textContent = payload.openai_enabled ? payload.model : "manual mode";
}

elements.fitMapButton.addEventListener("click", () => {
  if (state.map && state.markerBounds) {
    state.map.fitBounds(state.markerBounds, { padding: [42, 42], maxZoom: 14 });
  }
});

elements.topicChips.forEach((chip) => {
  chip.setAttribute("aria-pressed", "false");
  chip.addEventListener("click", () => {
    setActiveCategory(chip.dataset.category || "");
    elements.searchForm.requestSubmit();
  });
});

elements.booksPhotoInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  previewSelectedPhoto(file, elements.booksPhotoPreview, elements.booksPreviewPlaceholder);
});

elements.locationPhotoInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  previewSelectedPhoto(file, elements.locationPhotoPreview, elements.locationPreviewPlaceholder);
});

elements.useCaptureLocation.addEventListener("click", async () => {
  try {
    state.captureLocation = await requestLocation(elements.captureLocationStatus);
    elements.captureLocationStatus.textContent = `Attached ${formatNumber(state.captureLocation.latitude)}°, ${formatNumber(
      state.captureLocation.longitude
    )}° with ±${Math.round(state.captureLocation.accuracy_meters)}m accuracy.`;
  } catch (error) {
    elements.captureLocationStatus.textContent = error.message;
  }
});

elements.useSearchLocation.addEventListener("click", async () => {
  try {
    state.searchLocation = await requestLocation(elements.searchLocationStatus);
    state.searchLocation.source = "browser";
    elements.searchZipCode.value = "";
    elements.searchLocationStatus.textContent = `Using ${formatNumber(state.searchLocation.latitude)}°, ${formatNumber(
      state.searchLocation.longitude
    )}° for distance ranking.`;
  } catch (error) {
    elements.searchLocationStatus.textContent = error.message;
  }
});

elements.captureForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const booksFile = elements.booksPhotoInput.files?.[0];
  const locationFile = elements.locationPhotoInput.files?.[0];
  if (!booksFile) {
    setCallout("Pick a close-up books photo first. The locator photo is optional.", "error");
    return;
  }

  setCallout("Analyzing the books photo and preparing the locator image...", "muted");

  const formData = new FormData();
  formData.append("books_photo", booksFile);
  if (locationFile) {
    formData.append("location_photo", locationFile);
  }
  if (state.captureLocation) {
    formData.append("browser_latitude", state.captureLocation.latitude);
    formData.append("browser_longitude", state.captureLocation.longitude);
    formData.append("browser_accuracy_meters", state.captureLocation.accuracy_meters);
  }

  try {
    const draft = await fetchJSON("/api/analyze-photo", {
      method: "POST",
      body: formData,
    });
    renderDraft(draft);
  } catch (error) {
    setCallout(error.message, "error");
  }
});

elements.addBookRow.addEventListener("click", () => addBookRow());

elements.libraryDraftForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = collectDraftPayload();
  if (!payload.books.length) {
    setCallout("Add at least one book before saving.", "error");
    return;
  }

  try {
    const response = await fetchJSON("/api/libraries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    updateCounts(response.counts);
    await loadLibraries();
    setCallout("Library saved into the atlas. You can search it from the panel on the right.", "muted");
  } catch (error) {
    setCallout(error.message, "error");
  }
});

elements.searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = elements.searchQuery.value.trim();
  if (!query && !state.activeCategory) {
    elements.searchResults.innerHTML = `<div class="result-empty">Enter a title, author, ISBN, topic, or choose a category chip.</div>`;
    return;
  }

  const zipCode = elements.searchZipCode.value.trim();
  if (zipCode) {
    try {
      const location = await lookupZipCode(zipCode);
      state.searchLocation = { latitude: location.latitude, longitude: location.longitude, source: "zip" };
      elements.searchLocationStatus.textContent = `Using ZIP ${location.zipCode} (${location.label}) for distance ranking.`;
    } catch (error) {
      elements.searchLocationStatus.textContent = error.message;
      return;
    }
  } else if (state.searchLocation?.source !== "browser") {
    state.searchLocation = null;
    elements.searchLocationStatus.textContent = "Searching all libraries. Add a ZIP code to sort by distance.";
  }

  const payload = {
    query,
    category: state.activeCategory,
    latitude: state.searchLocation?.latitude ?? null,
    longitude: state.searchLocation?.longitude ?? null,
    radius_miles: elements.searchRadius.value ? Number(elements.searchRadius.value) : 25,
  };

  try {
    const response = await fetchJSON("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderSearchResults(response.results || []);
  } catch (error) {
    elements.searchResults.innerHTML = `<div class="result-empty">${escapeHtml(error.message)}</div>`;
  }
});

Promise.all([loadConfig(), loadLibraries()]).catch((error) => {
  setCallout(error.message, "error");
});
