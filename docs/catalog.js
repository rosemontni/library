function classificationLabel(book) {
  const labels = [];
  if (book.ddc_numbers?.length) labels.push(`Dewey: ${book.ddc_numbers.join("; ")}`);
  if (book.lcc_numbers?.length) labels.push(`LCC: ${book.lcc_numbers.join("; ")}`);
  return labels.length ? `${labels.join(" · ")} (work-level match; edition unverified)` : (book.classification_status === "pending" ? "Classification lookup pending" : "Classification needs review");
}

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


const catalog = { books: [], libraries: new Map(), page: 1, pageSize: 24 };
const ui = Object.fromEntries(["catalogForm", "catalogControls", "catalogQuery", "catalogSystem", "catalogStatus", "allBooksResults", "previousPage", "nextPage", "pageNumber", "retryAllBooks"].map(id => [id, document.getElementById(id)]));
function readFilters() {
  const params = new URLSearchParams(location.search);
  ui.catalogQuery.value = params.get("q") || "";
  ui.catalogSystem.value = ["dewey", "lcc", "review"].includes(params.get("system")) ? params.get("system") : "all";
  catalog.page = Math.max(1, Number.parseInt(params.get("page"), 10) || 1);
}
function rememberFilters() {
  const params = new URLSearchParams();
  if (ui.catalogQuery.value.trim()) params.set("q", ui.catalogQuery.value.trim());
  if (ui.catalogSystem.value !== "all") params.set("system", ui.catalogSystem.value);
  if (catalog.page > 1) params.set("page", catalog.page);
  history.pushState(null, "", location.pathname + (params.size ? "?" + params : ""));
}
function catalogCard(book) {
  const library = catalog.libraries.get(book.library_id);
  const classification = CatalogOrder.entry(book);
  const locationLabel = library?.official_address || library?.location_label || "Location shown on the map";
  const sourceLinks = (book.classification_sources || []).filter(url => /^https:\/\/openlibrary\.org\/works\/OL\d+W$/.test(url));
  return `<article class="result-card">
    <p class="catalog-call-number">${classification.number ? `${classification.system === "dewey" ? "Dewey" : "LCC"} ${escapeHtml(classification.number)}` : "Classification needs review"}</p>
    <h3>${escapeHtml(book.title || "Untitled")}</h3>
    ${book.author ? `<p class="book-author">${escapeHtml(book.author)}</p>` : ""}
    <p class="shelf-name">${escapeHtml(library?.csn || (library?.id ? `CSN-${library.id}` : ""))} · ${escapeHtml(library?.name || "Unknown shelf")}</p>
    ${library?.box_type === "reading_library" ? '<p><strong>Read on site; books stay here.</strong></p>' : ""}
    <p>${escapeHtml(locationLabel)}</p>
    <details class="book-details"><summary>Book details</summary>
      <p>${escapeHtml(classificationLabel(book))}</p>
      <p>Category: ${escapeHtml(book.genre || "Needs review")}</p>
      <p>${escapeHtml([book.publisher, book.published_year, book.format].filter(Boolean).join(" · "))}</p>
      ${book.isbn ? `<p>ISBN: ${escapeHtml(book.isbn)}</p>` : ""}
      ${sourceLinks.map(url => `<p><a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Classification source</a></p>`).join("")}
      ${book.notes ? `<p>${escapeHtml(book.notes)}</p>` : ""}
    </details>
    ${library ? `<a class="catalog-map-link" href="./index.html?library=${encodeURIComponent(library.id)}#mapTitle">Show on map</a>` : ""}
  </article>`;
}
function renderCatalog() {
  const terms = normalize(ui.catalogQuery.value).split(" ").filter(Boolean);
  const filtered = catalog.books.filter(book => {
    const system = CatalogOrder.entry(book).system;
    const blob = normalize([book.title, book.author, book.genre, book.publisher, book.isbn, ...(book.ddc_numbers || []), ...(book.lcc_numbers || [])].join(" "));
    return (ui.catalogSystem.value === "all" || ui.catalogSystem.value === system) && terms.every(term => blob.includes(term));
  });
  const pages = Math.max(1, Math.ceil(filtered.length / catalog.pageSize));
  catalog.page = Math.min(catalog.page, pages);
  const start = (catalog.page - 1) * catalog.pageSize;
  const books = filtered.slice(start, start + catalog.pageSize);
  let group = "";
  ui.allBooksResults.innerHTML = books.map(book => {
    const next = CatalogOrder.entry(book).group;
    const heading = next !== group ? `<h2 class="catalog-group">${escapeHtml(next)}</h2>` : "";
    group = next;
    return heading + catalogCard(book);
  }).join("") || `<p class="empty-state">${catalog.books.length ? "No books match these filters." : "No books are cataloged yet."}</p>`;
  ui.catalogStatus.textContent = filtered.length ? `Showing ${start + 1}–${start + books.length} of ${filtered.length} books · Dewey, then LCC, then awaiting review` : `${filtered.length} books`;
  ui.allBooksResults.setAttribute("aria-busy", "false");
  ui.previousPage.disabled = catalog.page <= 1;
  ui.nextPage.disabled = catalog.page >= pages;
  ui.pageNumber.textContent = `Page ${catalog.page} of ${pages}`;
}
async function loadCatalog() {
  ui.catalogControls.disabled = true;
  ui.previousPage.disabled = ui.nextPage.disabled = true;
  ui.retryAllBooks.hidden = true;
  ui.allBooksResults.setAttribute("aria-busy", "true");
  ui.catalogStatus.textContent = "Loading the book catalog…";
  try {
    const response = await fetch("./atlas-data.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Catalog unavailable");
    const data = await response.json();
    let overlay = {};
    try {
      const local = await fetch("./local-community-boxes.json", { cache: "no-store" });
      if (local.ok) overlay = await local.json();
    } catch (_) { /* Local overlay is optional. */ }
    const libraries = new Map((data.libraries || []).map(library => [library.id, library]));
    for (const library of overlay.libraries || []) if (!libraries.has(library.id)) libraries.set(library.id, library);
    catalog.libraries = libraries;
    const books = new Map((data.books || []).map(book => [String(book.id ?? book.book_id), book]));
    for (const book of overlay.books || []) if (!books.has(String(book.id ?? book.book_id))) books.set(String(book.id ?? book.book_id), book);
    catalog.books = [...books.values()].sort(CatalogOrder.compare);
    ui.catalogControls.disabled = false;
    renderCatalog();
  } catch (_) {
    ui.catalogStatus.textContent = "We couldn’t load the book catalog. Check your connection and try again.";
    ui.allBooksResults.setAttribute("aria-busy", "false");
    ui.retryAllBooks.hidden = false;
  }
}
ui.catalogForm.addEventListener("submit", event => { event.preventDefault(); catalog.page = 1; renderCatalog(); rememberFilters(); });
for (const [button, delta] of [[ui.previousPage, -1], [ui.nextPage, 1]]) button.addEventListener("click", () => {
  catalog.page += delta; renderCatalog(); rememberFilters();
  document.getElementById("allBooksTitle").focus();
});
ui.retryAllBooks.addEventListener("click", loadCatalog);
window.addEventListener("popstate", () => { readFilters(); renderCatalog(); });
readFilters();
loadCatalog();
