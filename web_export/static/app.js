const state = {
  data: null,
  periodIndex: 0,
  sortKey: "topBottomRatio",
  sortDirection: "desc",
  search: "",
  amcOnly: false,
};

const numberFormat = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const percentFormat = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });

document.addEventListener("DOMContentLoaded", async () => {
  const response = await fetch("data.json", { cache: "no-store" });
  state.data = await response.json();

  document.getElementById("searchInput").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    render();
  });

  document.getElementById("amcOnlyInput").addEventListener("change", (event) => {
    state.amcOnly = event.target.checked;
    render();
  });

  document.querySelectorAll("th[data-sort]").forEach((th) => {
    setHeaderWords(th, th.textContent);
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (state.sortKey === key) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDirection = key === "indexName" || key === "sourceUrl" ? "asc" : "desc";
      }
      render();
    });
  });

  renderTabs();
  renderMeta();
  render();
});

function renderTabs() {
  const tabs = document.getElementById("periodTabs");
  tabs.innerHTML = "";
  state.data.periods.forEach((period, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = period.label;
    button.className = index === state.periodIndex ? "active" : "";
    button.addEventListener("click", () => {
      state.periodIndex = index;
      renderTabs();
      render();
    });
    tabs.appendChild(button);
  });
}

function render() {
  const period = state.data.periods[state.periodIndex];
  const rows = sortedRows(filteredRows(period.rows));
  renderTable(period, rows);
  renderFooter();
}

function renderMeta() {
  const reportMeta = document.getElementById("reportMeta");
  const metadata = [
    ["Data updated up to", formatDateOnly(state.data.dataUpdatedThrough)],
  ];

  reportMeta.innerHTML = metadata.map(([label, value]) => `
    <div>
      <span>${label}</span>
      <strong>${value}</strong>
    </div>
  `).join("");

  const sourceList = document.getElementById("sourceList");
  sourceList.innerHTML = state.data.sources.map((source) => `
    <li>
      <span>${escapeHtml(source.text)}</span>
      <a href="${escapeHtml(source.url)}" aria-label="Open source">↗</a>
    </li>
  `).join("");
}

function filteredRows(rows) {
  return rows.filter((row) => {
    if (state.amcOnly && row.amcs.length === 0) return false;
    if (!state.search) return true;
    const haystack = `${row.indexName} ${row.amcs.join(" ")}`.toLowerCase();
    return haystack.includes(state.search);
  });
}

function sortedRows(rows) {
  const direction = state.sortDirection === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = sortValue(a, state.sortKey);
    const bv = sortValue(b, state.sortKey);
    if (typeof av === "string" || typeof bv === "string") {
      return String(av).localeCompare(String(bv)) * direction;
    }
    return ((av ?? Number.NEGATIVE_INFINITY) - (bv ?? Number.NEGATIVE_INFINITY)) * direction;
  });
}

function sortValue(row, key) {
  return row[key];
}

function renderTable(period, rows) {
  const tbody = document.getElementById("rankingBody");
  tbody.innerHTML = "";
  document.getElementById("rowCount").textContent = `${rows.length} rows`;
  setHeaderWords(
    document.getElementById("avgRollingHeader"),
    `Average ${period.rollingYears} Year Rolling Return (%)`
  );

  const fragment = document.createDocumentFragment();
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.indexName)}</td>
      <td>${formatPercent(row.cagr)}</td>
      <td>${formatPercent(row.stdDev)}</td>
      <td>${formatPercent(row.maxDrawdown)}</td>
      <td>${numberOrDash(row.sharpeRatio)}</td>
      <td>${numberOrDash(row.sortinoRatio)}</td>
      <td>${numberOrDash(row.yearsOfData)}</td>
      <td>${formatPercent(row.latest1YearReturn)}</td>
      <td>${formatPercent(row.latest3YearReturn)}</td>
      <td>${formatPercent(row.latest5YearReturn)}</td>
      <td>${formatPercent(row.latest7YearReturn)}</td>
      <td>${formatPercent(row.latest10YearReturn)}</td>
      <td>${formatPercent(row.averageRollingReturn)}</td>
      <td>${formatPercent(row.worstRollingReturn)}</td>
      <td>${formatPercent(row.bestRollingReturn)}</td>
      <td>${formatPercent(row.rollingReturnStdDev)}</td>
      <td>${numberOrDash(row.topQuartileCount)}</td>
      <td>${numberOrDash(row.bottomQuartileCount)}</td>
      <td>${numberOrDash(row.topBottomRatio)}</td>
      <td>${row.sourceUrl ? `<a class="source-link" href="${escapeHtml(row.sourceUrl)}" target="_blank" rel="noopener">Source</a>` : '<span class="muted">none</span>'}</td>
    `;
    fragment.appendChild(tr);
  }
  tbody.appendChild(fragment);
}

function renderFooter() {
  const date = new Date(state.data.generatedAt);
  document.getElementById("updatedAt").textContent = `Updated ${date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })}`;
}

function formatDateOnly(value) {
  if (!value) return "Not available";
  const date = new Date(`${value}T00:00:00`);
  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPercent(value) {
  return value === null || value === undefined ? "-" : `${percentFormat.format(value)}%`;
}

function numberOrDash(value) {
  return value === null || value === undefined ? "-" : numberFormat.format(value);
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

function setHeaderWords(th, label) {
  th.textContent = "";
  for (const word of String(label).trim().split(/\s+/)) {
    const span = document.createElement("span");
    span.textContent = word;
    th.appendChild(span);
  }
}
