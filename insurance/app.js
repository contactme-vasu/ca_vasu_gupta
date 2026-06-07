const state = {
  data: null,
  sortKey: "4-yr Avg CSR (%)",
  sortDirection: "desc",
  search: "",
  completeOnly: false,
};

const numberFormat = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const integerFormat = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const percentFormat = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
});

document.addEventListener("DOMContentLoaded", async () => {
  const response = await fetch("data.json", { cache: "no-store" });
  state.data = await response.json();

  document.getElementById("searchInput").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    render();
  });

  document.getElementById("rankSelect").addEventListener("change", (event) => {
    state.sortKey = event.target.value;
    state.sortDirection = event.target.value === "3-yr Avg Complaints" ? "asc" : "desc";
    render();
  });

  document.getElementById("completeOnlyInput").addEventListener("change", (event) => {
    state.completeOnly = event.target.checked;
    render();
  });

  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (state.sortKey === key) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDirection = key === "Company" || key === "3-yr Avg Complaints" ? "asc" : "desc";
      }
      render();
    });
  });

  render();
});

function render() {
  const rows = sortedRows(filteredRows(state.data.rows));
  renderTable(rows);
  renderFooter();
}

function filteredRows(rows) {
  return rows.filter((row) => {
    if (state.completeOnly && !hasCompleteKeyMetrics(row)) return false;
    if (!state.search) return true;
    return String(row.Company).toLowerCase().includes(state.search);
  });
}

function hasCompleteKeyMetrics(row) {
  return [
    "Track Record (Years)",
    "4-yr Avg CSR (%)",
    "3-yr Avg Complaints",
    "3-yr Avg ICR (%)",
  ].every((key) => row[key] !== null && row[key] !== undefined);
}

function sortedRows(rows) {
  const direction = state.sortDirection === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = a[state.sortKey];
    const bv = b[state.sortKey];
    if (typeof av === "string" || typeof bv === "string") {
      return String(av ?? "").localeCompare(String(bv ?? "")) * direction;
    }
    return ((av ?? Number.NEGATIVE_INFINITY) - (bv ?? Number.NEGATIVE_INFINITY)) * direction;
  });
}

function renderTable(rows) {
  const tbody = document.getElementById("companyBody");
  tbody.innerHTML = "";
  document.getElementById("rowCount").textContent = `${rows.length} rows`;

  const fragment = document.createDocumentFragment();
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.Company)}</td>
      <td>${formatInteger(row["Track Record (Years)"])}</td>
      <td>${formatInteger(row["3-yr Avg Complaints"])}</td>
      <td>${formatPercent(row["4-yr Avg CSR (%)"])}</td>
      <td>${formatPercent(row["3-yr Avg ICR (%)"])}</td>
    `;
    fragment.appendChild(tr);
  }
  tbody.appendChild(fragment);
}

function renderFooter() {
  const date = new Date(state.data.generatedAt);
  document.getElementById("handbookLabel").textContent = `IRDAI Handbook ${state.data.dataUpdatedThrough}`;
  document.getElementById("sourceLabel").textContent = `CA Vasu Gupta. Source: ${state.data.source}. Company names are data references only.`;
  document.getElementById("updatedAt").textContent = `Updated ${date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })}`;
}

function maxBy(rows, key) {
  return rows.reduce((best, row) => {
    if (row[key] === null || row[key] === undefined) return best;
    if (!best || row[key] > best[key]) return row;
    return best;
  }, null);
}

function minBy(rows, key) {
  return rows.reduce((best, row) => {
    if (row[key] === null || row[key] === undefined) return best;
    if (!best || row[key] < best[key]) return row;
    return best;
  }, null);
}

function formatPercent(value) {
  return value === null || value === undefined ? "-" : `${percentFormat.format(value)}%`;
}

function formatInteger(value) {
  return value === null || value === undefined ? "-" : integerFormat.format(value);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}
