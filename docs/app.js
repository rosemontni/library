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
  zipCode: document.getElementById("zipCode"),
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

function formatCount(count, singular, plural = `${singular}s`) {
  const value = Number(count || 0);
  return `${value} ${value === 1 ? singular : plural}`;
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

function hasCoordinates(library) {
  return library && library.latitude !== null && library.latitude !== undefined && library.longitude !== null && library.longitude !== undefined;
}

function toTitleCase(value) {
  return String(value || "")
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      if (word.toUpperCase() === word && word.length <= 4) {
        return word;
      }
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

function primaryGenre(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "Uncategorized";
  }

  return toTitleCase(raw.split(/[\/|,;]/)[0].replace(/\s+/g, " ").trim() || "Uncategorized");
}

function buildLibraryGenreSummary(libraryId) {
  const books = Array.isArray(state.data?.books) ? state.data.books : [];
  const genres = new Map();

  books
    .filter((book) => String(book.library_id) === String(libraryId))
    .forEach((book) => {
      const genreName = primaryGenre(book.genre);
      const title = String(book.title || "Untitled").trim() || "Untitled";
      if (!genres.has(genreName)) {
        genres.set(genreName, {
          name: genreName,
          count: 0,
          books: new Map(),
        });
      }

      const genre = genres.get(genreName);
      genre.count += 1;
      genre.books.set(title, (genre.books.get(title) || 0) + 1);
    });

  return Array.from(genres.values())
    .map((genre) => ({
      name: genre.name,
      count: genre.count,
      books: Array.from(genre.books.entries())
        .map(([title, count]) => ({ title, count }))
        .sort((a, b) => b.count - a.count || a.title.localeCompare(b.title))
        .slice(0, 5),
    }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    .slice(0, 5);
}

function renderGenreChips(summary) {
  if (!summary.length) {
    return `<span class="genre-chip muted">No genres yet</span>`;
  }

  return summary
    .map((genre) => `<span class="genre-chip">${escapeHtml(genre.name)} <b>${Number(genre.count || 0)}</b></span>`)
    .join("");
}

function renderGenreSummary(summary, title = "Top genres") {
  if (!summary.length) {
    return `<div class="genre-summary empty">No genre summary is available for this library yet.</div>`;
  }

  return `
    <div class="genre-summary">
      <p class="genre-summary-title">${escapeHtml(title)}</p>
      ${summary
        .map(
          (genre) => `
            <section class="genre-group">
              <div class="genre-heading">
                <strong>${escapeHtml(genre.name)}</strong>
                <span>${formatCount(genre.count, "book")}</span>
              </div>
              <ol>
                ${genre.books
                  .map(
                    (book) => `
                      <li>
                        <span>${escapeHtml(book.title)}</span>
                        <b>${Number(book.count || 0)}</b>
                      </li>
                    `
                  )
                  .join("")}
              </ol>
            </section>
          `
        )
        .join("")}
    </div>
  `;
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
  const genreSummary = buildLibraryGenreSummary(library.id);
  return `
    <article class="popup">
      <strong>${escapeHtml(library.name)}</strong>
      <p>${escapeHtml(library.description || "No description saved.")}</p>
      <small>${Number(library.book_count || 0)} books at ${formatCoordinate(library.latitude)}, ${formatCoordinate(library.longitude)}</small>
      ${renderGenreSummary(genreSummary, "Top genres here")}
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
    const genreSummary = buildLibraryGenreSummary(library.id);
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
      <div class="genre-chips" aria-label="Top genres">${renderGenreChips(genreSummary)}</div>
      <details class="genre-details">
        <summary>Top books by genre</summary>
        ${renderGenreSummary(genreSummary, "Top 5 genres, top 5 books")}
      </details>
    `;
    card.querySelector(".genre-details")?.addEventListener("click", (event) => event.stopPropagation());
    card.querySelector(".genre-details")?.addEventListener("keydown", (event) => event.stopPropagation());
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

function setLocation(latitude, longitude, label = "Using your location for distance ranking.", source = "manual") {
  state.searchLocation = { latitude: Number(latitude), longitude: Number(longitude), source };
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
      elements.zipCode.value = "";
      setLocation(position.coords.latitude, position.coords.longitude, "Location ready. Results will be sorted by distance.", "browser");
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

elements.searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const zipCode = elements.zipCode.value.trim();
  if (zipCode) {
    try {
      const location = await lookupZipCode(zipCode);
      setLocation(
        location.latitude,
        location.longitude,
        `Using ZIP ${location.zipCode} (${location.label}) for distance ranking.`,
        "zip"
      );
    } catch (error) {
      elements.locationStatus.textContent = error.message;
      return;
    }
  } else if (state.searchLocation?.source !== "browser") {
    state.searchLocation = null;
    elements.locationStatus.textContent = "Searching all libraries. Add a ZIP code to sort by distance.";
  }
  runSearch();
});

elements.useLocation.addEventListener("click", useBrowserLocation);

elements.quickSearches.forEach((button) => {
  button.addEventListener("click", () => {
    elements.searchQuery.value = button.dataset.query || "";
    elements.searchForm.requestSubmit();
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
