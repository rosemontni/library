const state = {
  captureLocation: null,
  searchLocation: null,
  currentDraft: null,
};

const elements = {
  libraryCount: document.getElementById("libraryCount"),
  bookCount: document.getElementById("bookCount"),
  modelName: document.getElementById("modelName"),
  captureForm: document.getElementById("captureForm"),
  photoInput: document.getElementById("photoInput"),
  photoPreview: document.getElementById("photoPreview"),
  previewPlaceholder: document.getElementById("previewPlaceholder"),
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
  searchLatitude: document.getElementById("searchLatitude"),
  searchLongitude: document.getElementById("searchLongitude"),
  searchRadius: document.getElementById("searchRadius"),
  useSearchLocation: document.getElementById("useSearchLocation"),
  searchLocationStatus: document.getElementById("searchLocationStatus"),
  searchResults: document.getElementById("searchResults"),
  bookRowTemplate: document.getElementById("bookRowTemplate"),
};

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

function previewSelectedPhoto(file) {
  if (!file) {
    elements.photoPreview.hidden = true;
    elements.previewPlaceholder.hidden = false;
    return;
  }

  const url = URL.createObjectURL(file);
  elements.photoPreview.src = url;
  elements.photoPreview.hidden = false;
  elements.previewPlaceholder.hidden = true;
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

function renderSearchResults(results) {
  elements.searchResults.innerHTML = "";

  if (!results.length) {
    elements.searchResults.innerHTML = `<div class="result-empty">No matching books were found within the selected radius yet.</div>`;
    return;
  }

  results.forEach((result) => {
    const article = document.createElement("article");
    article.className = "result-card";

    const distanceLabel = formatDistance(result.distance_miles);
    const libraryCoords =
      result.library.latitude !== null && result.library.longitude !== null
        ? `${formatNumber(result.library.latitude)}°, ${formatNumber(result.library.longitude)}°`
        : "Coordinates not saved";

    article.innerHTML = `
      <div class="result-head">
        <div>
          <h3 class="result-title">${escapeHtml(result.title)}</h3>
          <p>${escapeHtml(result.author || "Unknown author")}</p>
        </div>
        <span class="distance-pill">${escapeHtml(distanceLabel)}</span>
      </div>
      <div class="result-meta">
        ${result.isbn ? `<span>ISBN ${escapeHtml(result.isbn)}</span>` : ""}
        ${result.genre ? `<span>${escapeHtml(result.genre)}</span>` : ""}
        ${result.format ? `<span>${escapeHtml(result.format)}</span>` : ""}
        ${result.condition ? `<span>${escapeHtml(result.condition)}</span>` : ""}
      </div>
      <div class="result-library">
        <strong>${escapeHtml(result.library.name)}</strong><br />
        ${escapeHtml(result.library.description || "No library description saved yet.")}<br />
        <small>${escapeHtml(libraryCoords)} · source: ${escapeHtml(result.library.location_source || "manual")}</small>
      </div>
    `;

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

elements.photoInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  previewSelectedPhoto(file);
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
    elements.searchLatitude.value = state.searchLocation.latitude;
    elements.searchLongitude.value = state.searchLocation.longitude;
    elements.searchLocationStatus.textContent = `Using ${formatNumber(state.searchLocation.latitude)}°, ${formatNumber(
      state.searchLocation.longitude
    )}° for distance ranking.`;
  } catch (error) {
    elements.searchLocationStatus.textContent = error.message;
  }
});

elements.captureForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = elements.photoInput.files?.[0];
  if (!file) {
    setCallout("Pick a sidewalk library photo first.", "error");
    return;
  }

  setCallout("Analyzing photo and extracting shelf metadata...", "muted");

  const formData = new FormData();
  formData.append("photo", file);
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
    setCallout("Library saved into the atlas. You can search it from the panel on the right.", "muted");
  } catch (error) {
    setCallout(error.message, "error");
  }
});

elements.searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = elements.searchQuery.value.trim();
  if (!query) {
    elements.searchResults.innerHTML = `<div class="result-empty">Enter a title, author, or ISBN to search the atlas.</div>`;
    return;
  }

  const payload = {
    query,
    latitude: elements.searchLatitude.value ? Number(elements.searchLatitude.value) : null,
    longitude: elements.searchLongitude.value ? Number(elements.searchLongitude.value) : null,
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

loadConfig().catch((error) => {
  setCallout(error.message, "error");
});
