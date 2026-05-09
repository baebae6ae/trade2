/* static/js/common.js */

// ── 시계 ──────────────────────────────────────────
function updateClock() {
  const el = document.getElementById("clockText");
  if (!el) return;
  el.textContent = new Date().toLocaleTimeString("ko-KR",
    {hour:"2-digit", minute:"2-digit", second:"2-digit", hour12:false});
}
setInterval(updateClock, 1000);
updateClock();

// ── 내비 활성 표시 ─────────────────────────────────
(function markActiveNav() {
  const path = window.location.pathname.split("?")[0].replace(/\/$/, "") || "/";
  document.querySelectorAll(".nav-link").forEach(a => {
    const href = (a.getAttribute("href") || "").replace(/\/$/, "") || "/";
    if (href === path) a.classList.add("active");
  });
})();

// ── 숫자 포맷 ──────────────────────────────────────
function fmt(v, digits = 2) {
  if (v == null || isNaN(v)) return "—";
  return Number(v).toLocaleString("ko-KR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}
function fmtVol(v) {
  if (!v) return "—";
  if (v >= 1e12) return (v / 1e12).toFixed(1) + "조";
  if (v >= 1e8)  return (v / 1e8).toFixed(0)  + "억";
  if (v >= 1e4)  return (v / 1e4).toFixed(0)  + "만";
  return v.toLocaleString("ko-KR");
}
function fmtPct(v) {
  if (v == null) return "—";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

// ── FIS 색상 / 레이블 ────────────────────────────────
function fisColor(fis) {
  if (fis >= 70)  return "#D32F2F";
  if (fis >= 40)  return "#E57373";
  if (fis >= 10)  return "#F9A825";
  if (fis >= -20) return "#64B5F6";
  if (fis >= -50) return "#1565C0";
  return "#0D47A1";
}
function fisLabel(fis) {
  if (fis >= 70)  return "강한 상승형";
  if (fis >= 40)  return "우호적 추세형";
  if (fis >= 10)  return "중립 관망형";
  if (fis >= -20) return "약세 주의형";
  if (fis >= -50) return "하락 압력형";
  return "강한 하락형";
}

// ── RSI / RVOL 상태 텍스트 ──────────────────────────────
function rsiStatus(rsi) {
  if (rsi >= 70) return "과매수";
  if (rsi >= 60) return "상승 강세";
  if (rsi >= 40) return "중립";
  if (rsi >= 30) return "하락 약세";
  return "과매도";
}
function rsiColor(rsi) {
  if (rsi >= 70) return "var(--bear)";
  if (rsi >= 60) return "var(--bull)";
  if (rsi <= 30) return "var(--bull)";
  return "var(--text2)";
}
function rvolStatus(rvol) {
  if (rvol >= 2.0) return "폭발적 거래량";
  if (rvol >= 1.5) return "강한 거래량";
  if (rvol >= 0.8) return "보통";
  return "거래 부진";
}

// ── 종목 분석 이동 ────────────────────────────────────
function goAnalyze(ticker) {
  window.location.href = `/analyze?ticker=${encodeURIComponent(ticker)}`;
}

// ── 검색 ──────────────────────────────────────────────
let _searchTimer = null;
const _searchInput    = () => document.getElementById("searchInput");
const _searchDropdown = () => document.getElementById("searchDropdown");

document.addEventListener("DOMContentLoaded", () => {
  const inp = _searchInput();
  if (!inp) return;
  inp.addEventListener("input", () => {
    clearTimeout(_searchTimer);
    const q = inp.value.trim();
    if (!q) { closeDropdown(); return; }
    _searchTimer = setTimeout(() => _execSearch(q), 350);
  });
  inp.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
  document.addEventListener("click", e => {
    if (!e.target.closest(".topbar-search")) closeDropdown();
  });
});

async function _execSearch(q) {
  const dd = _searchDropdown();
  if (!dd) return;
  try {
    const data = await fetch(`/api/search?q=${encodeURIComponent(q)}`).then(r => r.json());
    if (!data.ok || !data.results.length) { closeDropdown(); return; }
    dd.innerHTML = data.results.slice(0, 7).map(r => `
      <div class="dd-item" onclick="goAnalyze('${r.symbol}')">
        <div>
          <div class="dd-name">${r.name || r.symbol}</div>
          <div class="dd-sym">${r.symbol}</div>
        </div>
        <span class="dd-exch">${r.exchange || r.type || ""}</span>
      </div>`).join("");
    dd.classList.remove("hidden");
  } catch (e) { closeDropdown(); }
}

function doSearch() {
  const v = _searchInput()?.value.trim();
  if (v) goAnalyze(v);
}
function closeDropdown() {
  _searchDropdown()?.classList.add("hidden");
}

// ── 토스트 ────────────────────────────────────────────
function showToast(msg, type = "success") {
  let el = document.getElementById("toast");
  if (!el) { el = document.createElement("div"); el.id = "toast"; document.body.appendChild(el); }
  el.textContent = msg;
  el.className = `toast toast-${type} show`;
  setTimeout(() => el.classList.remove("show"), 3200);
}

// Mobile nav active mark
(function markMobileNav() {
  const path = window.location.pathname.split("?")[0].replace(/\/$/, "") || "/";
  document.querySelectorAll(".mn-item").forEach(a => {
    const href = (a.getAttribute("href") || "").replace(/\/$/, "") || "/";
    if (href === path) a.classList.add("active");
  });
})();
