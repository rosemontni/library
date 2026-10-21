/* Shared, testable shelf ordering. Values remain source-backed classifications. */
const CatalogOrder = (() => {
  const text = new Intl.Collator("en", { sensitivity: "base", numeric: true });
  function compareDewey(a, b) {
    const [wholeA, fractionA = ""] = a.split(".");
    const [wholeB, fractionB = ""] = b.split(".");
    return Number(wholeA) - Number(wholeB) || fractionA.padEnd(Math.max(fractionA.length, fractionB.length), "0").localeCompare(fractionB.padEnd(Math.max(fractionA.length, fractionB.length), "0"));
  }
  function compareLcc(a, b) {
    const pattern = /^([A-Z]{1,3})(\d+)(?:\.(\d+))?(.*)$/;
    const x = a.match(pattern), y = b.match(pattern);
    if (!x || !y) return text.compare(a, b);
    // Cutter numbers sort as decimals: .A19 precedes .A2.
    const cutter = tail => tail.replace(/([A-Z])(\d+)/g, (_, letter, digits) => letter + digits.padEnd(16, "0"));
    return x[1].localeCompare(y[1]) || compareDewey(x[2] + "." + (x[3] || "0"), y[2] + "." + (y[3] || "0")) || cutter(x[4]).localeCompare(cutter(y[4]));
  }
  function entry(book) {
    const dewey = (book.ddc_numbers || []).filter(n => /^\d{3}(?:\.\d+)?$/.test(n)).sort(compareDewey);
    if (dewey.length) return { rank: 0, system: "dewey", number: dewey[0], group: dewey[0][0] + "00–" + dewey[0][0] + "99" };
    const lcc = (book.lcc_numbers || []).filter(n => /^[A-Z]{1,3}\d/.test(n)).sort(compareLcc);
    if (lcc.length) return { rank: 1, system: "lcc", number: lcc[0], group: "LCC · " + lcc[0].match(/^[A-Z]+/)[0] };
    return { rank: 2, system: "review", number: "", group: "Classification awaiting review" };
  }
  function compare(a, b) {
    const x = entry(a), y = entry(b);
    return x.rank - y.rank || (x.rank === 0 ? compareDewey(x.number, y.number) : compareLcc(x.number, y.number)) || text.compare(a.title || "", b.title || "") || text.compare(a.author || "", b.author || "") || Number(a.id || 0) - Number(b.id || 0);
  }
  return { entry, compare, compareDewey, compareLcc };
})();
if (typeof module !== "undefined") module.exports = CatalogOrder;
