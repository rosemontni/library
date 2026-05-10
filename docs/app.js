const state = {
  data: null,
  librariesById: new Map(),
  searchLocation: null,
  map: null,
  markers: new Map(),
  markerBounds: null,
};

const elements = {
  libraryCount: document.getElementById("libraryCount"),
  bookCount: document.getElementById("bookCount"),
  generatedAt: document.getElementById("generatedAt"),
  searchForm: document.getElementById("searchForm"),
  searchQuery: document.getElementById("searchQuery"),
  latitude: document.getElementById("latitude"),
  longitude: document.getElementById("longitude"),
  radiusMiles: document.getElementById("radiusMiles"),
  useLocation: document.getElementById("useLocation"),
  locationStatus: document.getElementById("locationStatus"),
  quickSearches: Array.from(document.querySelectorAll("[data-query]")),
  results: document.getElementById("results"),
  map: document.getElementById("map"),
  mapStatus: document.getElementById("mapStatus"),
  fitMarkers: document.getElementById("fitMarkers"),
  libraryList: document.getElementById("libraryList"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalize(value) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatCoordinate(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(4) : "unknown";
}

function formatGeneratedAt(value) {
  if (!value) {
    return "Snapshot date unavailable";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return `Snapshot ${value}`;
  }
  return `Snapshot ${date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`;
}

function hasCoordinates(library) {
  return library && library.latitude !== null && library.latitude !== undefined && library.longitude !== null && library.longitude !== undefined;
}

function haversineMiles(lat1, lon1, lat2, lon2) {
  const earthRadiusMiles = 3958.7613;
  const toRadians = (degrees) => (degrees * Math.PI) / 180;
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) ** 2;
  return earthRadiusMiles * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function bookSearchBlob(book) {
  return normalize([
    book.title,
    book.author,
    book.isbn,
    book.publisher,
    book.published_year,
    book.genre,
    book.format,
    book.notes,
  ].join(" "));
}

function scoreBook(book, terms, library, distanceMiles) {
  const title = normalize(book.title);
  const author = normalize(book.author);
  const genre = normalize(book.genre);
  let score = Number(book.confidence || 0) * 4;

  terms.forEach((term) => {
    if (title === term) score += 80;
    if (title.startsWith(term)) score += 36;
    if (title.includes(term)) score += 24;
    if (author.includes(term)) score += 18;
    if (genre.includes(term)) score += 10;
  });

  if (library && hasCoordinates(library)) {
    score += 4;
  }
  if (distanceMiles !== null && distanceMiles !== undefined) {
    score += Math.max(0, 25 - distanceMiles);
  }
  return score;
}

function searchBooks(query) {
  const normalizedQuery = normalize(query);
  const terms = normalizedQuery.split(" ").filter(Boolean);
  const radius = Number(elements.radiusMiles.value);
  const hasRadius = Number.isFinite(radius) && radius > 0;
  const origin = state.searchLocation;

  if (!terms.length) {
    return [];
  }

  return state.data.books
    .map((book) => {
      const library = state.librariesById.get(book.library_id);
      const blob = bookSearchBlob(book);
      const matches = terms.every((term) => blob.includes(term));
      if (!matches) {
        return null;
      }

      let distanceMiles = null;
      if (origin && library && hasCoordinates(library)) {
        distanceMiles = haversineMiles(origin.latitude, origin.longitude, Number(library.latitude), Number(library.longitude));
        if (hasRadius && distanceMiles > radius) {
          return null;
        }
      }

      return {
        book,
        library,
        distanceMiles,
        score: scoreBook(book, terms, library, distanceMiles),
      };
    })
    .filter(Boolean)
    .sort((a, b) => {
      if (a.distanceMiles !== null && b.distanceMiles !== null && a.distanceMiles !== b.distanceMiles) {
        return a.distanceMiles - b.distanceMiles;
      }
      return b.score - a.score || a.book.title.localeCompare(b.book.title);
    })
    .slice(0, 40);
}

function initMap() {
  if (state.map || !elements.map) {
    return;
  }

  if (!window.L) {
    elements.map.innerHTML = `<div class="map-loading">Map library unavailable. The search still works.</div>`;
    elements.mapStatus.textContent = "Leaflet did not load, so the map is unavailable.";
    return;
  }

  elements.map.innerHTML = "";
  state.map = L.map(elements.map, {
    zoomControl: true,
    scrollWheelZoom: true,
  }).setView([39.1, -77.1], 10);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(state.map);
}

function markerIcon(bookCount = 0) {
  return L.divIcon({
    className: "atlas-marker",
    html: `<span><b>${Number(bookCount || 0)}</b></span>`,
    iconSize: [40, 46],
    iconAnchor: [20, 42],
    popupAnchor: [0, -38],
  });
}

function popupHtml(library) {
  const samples = (library.sample_books || [])
    .slice(0, 5)
    .map((title) => `<li>${escapeHtml(title)}</li>`)
    .join("");
  return `
    <article class="popup">
      <strong>${escapeHtml(library.name)}</strong>
      <p>${escapeHtml(library.description || "No description saved.")}</p>
      <small>${Number(library.book_count || 0)} books at ${formatCoordinate(library.latitude)}, ${formatCoordinate(library.longitude)}</small>
      ${samples ? `<ul>${samples}</ul>` : ""}
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

  const coordinates = [];
  libraries.filter(hasCoordinates).forEach((library) => {
    const position = [Number(library.latitude), Number(library.longitude)];
    const marker = L.marker(position, { icon: markerIcon(library.book_count) })
      .addTo(state.map)
      .bindPopup(popupHtml(library), { maxWidth: 300 });
    state.markers.set(library.id, marker);
    coordinates.push(position);
  });

  if (coordinates.length) {
    state.markerBounds = L.latLngBounds(coordinates);
    state.map.fitBounds(state.markerBounds, { padding: [46, 46], maxZoom: 13 });
    elements.mapStatus.textContent = `${coordinates.length} mapped libraries. Scroll, pinch, or double-click to zoom.`;
  } else {
    elements.mapStatus.textContent = "No geolocated libraries in this snapshot.";
  }
}

function focusLibrary(libraryId) {
  const library = state.librariesById.get(libraryId);
  const marker = state.markers.get(libraryId);
  if (!library || !marker || !state.map || !hasCoordinates(library)) {
    return;
  }
  state.map.flyTo([Number(library.latitude), Number(library.longitude)], Math.max(state.map.getZoom(), 15), { duration: 0.7 });
  marker.openPopup();
}

function renderLibraries(libraries) {
  elements.libraryList.innerHTML = "";
  if (!libraries.length) {
    elements.libraryList.innerHTML = `<div class="empty-state">No libraries are available in this snapshot yet.</div>`;
    return;
  }

  libraries.forEach((library) => {
    const card = document.createElement("article");
    card.className = "library-card";
    card.tabIndex = hasCoordinates(library) ? 0 : -1;
    card.innerHTML = `
      <h3>${escapeHtml(library.name)}</h3>
      <p>${escapeHtml(library.description || "No description saved.")}</p>
      <div class="card-meta">
        <span>${Number(library.book_count || 0)} books</span>
        <span>${formatCoordinate(library.latitude)}, ${formatCoordinate(library.longitude)}</span>
      </div>
    `;
    if (hasCoordinates(library)) {
      card.addEventListener("click", () => focusLibrary(library.id));
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          focusLibrary(library.id);
        }
      });
    }
    elements.libraryList.appendChild(card);
  });
}

function renderResults(results, query) {
  if (!query.trim()) {
    elements.results.innerHTML = `<div class="empty-state">Search for a title, author, ISBN, publisher, or topic to find matching books.</div>`;
    return;
  }

  if (!results.length) {
    elements.results.innerHTML = `<div class="empty-state">No books matched "${escapeHtml(query)}" in this snapshot. Try a broader term.</div>`;
    return;
  }

  elements.results.innerHTML = "";
  const heading = document.createElement("div");
  heading.className = "note";
  heading.textContent = `${results.length} result${results.length === 1 ? "" : "s"} for "${query}".`;
  elements.results.appendChild(heading);

  results.forEach(({ book, library, distanceMiles }) => {
    const card = document.createElement("article");
    card.className = "result-card";
    const distance = distanceMiles === null || distanceMiles === undefined ? "" : `<span>${distanceMiles.toFixed(1)} mi away</span>`;
    card.innerHTML = `
      <div>
        <h3>${escapeHtml(book.title)}</h3>
        <p>${escapeHtml([book.author, book.genre, book.publisher, book.published_year].filter(Boolean).join(" · ") || "Metadata incomplete")}</p>
      </div>
      <div class="card-meta">
        <span>${escapeHtml(library?.name || "Unknown library")}</span>
        <span>${escapeHtml(book.format || "format unknown")}</span>
        ${distance}
      </div>
      ${book.notes ? `<p>${escapeHtml(book.notes)}</p>` : ""}
    `;

    if (library && hasCoordinates(library)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.textContent = "Show on map";
      button.addEventListener("click", () => focusLibrary(library.id));
      card.appendChild(button);
    }

    elements.results.appendChild(card);
  });
}

function runSearch() {
  const query = elements.searchQuery.value;
  renderResults(searchBooks(query), query);
}

function setLocation(latitude, longitude, label = "Using your location for distance ranking.") {
  state.searchLocation = { latitude: Number(latitude), longitude: Number(longitude) };
  elements.latitude.value = state.searchLocation.latitude.toFixed(6);
  elements.longitude.value = state.searchLocation.longitude.toFixed(6);
  elements.locationStatus.textContent = label;
}

async function useBrowserLocation() {
  if (!navigator.geolocation) {
    elements.locationStatus.textContent = "This browser does not support geolocation.";
    return;
  }

  elements.locationStatus.textContent = "Requesting location permission...";
  navigator.geolocation.getCurrentPosition(
    (position) => {
      setLocation(position.coords.latitude, position.coords.longitude, "Location ready. Results will be sorted by distance.");
      runSearch();
    },
    (error) => {
      elements.locationStatus.textContent = error.message || "Location permission was denied.";
    },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
  );
}

async function loadData() {
  const response = await fetch("./atlas-data.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Could not load atlas-data.json");
  }
  state.data = await response.json();
  state.librariesById = new Map((state.data.libraries || []).map((library) => [library.id, library]));

  elements.libraryCount.textContent = state.data.counts?.libraries ?? state.data.libraries?.length ?? 0;
  elements.bookCount.textContent = state.data.counts?.books ?? state.data.books?.length ?? 0;
  elements.generatedAt.textContent = formatGeneratedAt(state.data.generated_at);

  renderMap(state.data.libraries || []);
  renderLibraries(state.data.libraries || []);
  renderResults([], "");
}

elements.searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const lat = Number(elements.latitude.value);
  const lon = Number(elements.longitude.value);
  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    setLocation(lat, lon, "Using entered coordinates for distance ranking.");
  }
  runSearch();
});

elements.useLocation.addEventListener("click", useBrowserLocation);

elements.quickSearches.forEach((button) => {
  button.addEventListener("click", () => {
    elements.searchQuery.value = button.dataset.query || "";
    runSearch();
  });
});

elements.fitMarkers.addEventListener("click", () => {
  if (state.map && state.markerBounds) {
    state.map.fitBounds(state.markerBounds, { padding: [46, 46], maxZoom: 13 });
  }
});

loadData().catch((error) => {
  elements.map.innerHTML = `<div class="map-loading">Could not load the atlas snapshot.</div>`;
  elements.results.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  elements.generatedAt.textContent = "Snapshot failed to load";
});
