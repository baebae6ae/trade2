/* static/js/dashboard.js */

// ── 시장 지수 데이터 ──────────────────────────────────
async function loadMarket() {
  try {
    const data = await fetch("/api/market").then(r => r.json());
    if (!data.ok) return;
    renderTickerStrip(data.data);
    renderQuotes("krQuotes", data.data.KR, "krUpdated");
    renderQuotes("usQuotes", data.data.US, "usUpdated");
  } catch(e) { console.error("market load error", e); }
}

function renderTickerStrip(marketData) {
  const track = document.getElementById("tickerTrack");
  if (!track) return;
  const all = [...(marketData.KR||[]), ...(marketData.US||[])];
  const html = all.map(item => {
    const pct = item.change_pct;
    const cls = pct > 0 ? "bull" : pct < 0 ? "bear" : "flat";
    const sign = pct > 0 ? "+" : "";
    return `<div class="ticker-item">
      <span class="ti-name">${item.name}</span>
      <span class="ti-price">${item.price != null ? fmt(item.price) : "—"}</span>
      <span class="ti-chg ${cls}">${pct != null ? sign+pct.toFixed(2)+"%" : "—"}</span>
    </div>`;
  }).join("");
  track.innerHTML = html + html;
}

function renderQuotes(containerId, items, updatedId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const now = new Date().toLocaleTimeString("ko-KR", {hour:"2-digit",minute:"2-digit"});
  const updEl = document.getElementById(updatedId);
  if (updEl) updEl.textContent = now + " 기준";

  el.innerHTML = (items || []).map(item => {
    const pct    = item.change_pct;
    const dirCls = pct > 0 ? "bull" : pct < 0 ? "bear" : "flat";
    const sign   = pct > 0 ? "+" : "";
    const abssign= item.change > 0 ? "+" : "";
    const arrow  = pct > 0 ? "▲" : pct < 0 ? "▼" : "—";
    // bar width (max 4% = 100%)
    const barW   = pct != null ? Math.min(Math.abs(pct) / 4 * 100, 100) : 0;
    return `
      <div class="mq-row" onclick="goAnalyze('${item.ticker}')">
        <div class="mq-left">
          <span class="mq-name">${item.name}</span>
          <span class="mq-arrow ${dirCls}">${arrow}</span>
        </div>
        <div class="mq-right">
          <div class="mq-price">${item.price != null ? fmt(item.price) : "—"}</div>
          <div class="mq-chg-row">
            <span class="mq-pct ${dirCls}">${pct != null ? sign+pct.toFixed(2)+"%" : "—"}</span>
            <span class="mq-abs ${dirCls}">${item.change != null ? abssign+fmt(item.change) : ""}</span>
          </div>
          <div class="mq-bar-wrap">
            <div class="mq-bar ${dirCls}" style="width:${barW}%"></div>
          </div>
        </div>
      </div>`;
  }).join("");
}

// ── 마켓맵 ────────────────────────────────────────────
async function loadMarketMap(region) {
  const bodyId = region === "KR" ? "krMapBody" : "usMapBody";
  const body   = document.getElementById(bodyId);
  if (!body) return;
  body.innerHTML = '<div class="map-loading">로딩 중…</div>';
  try {
    const data = await fetch(`/api/marketmap/${region}`).then(r => r.json());
    if (!data.ok || !data.data.length) {
      body.innerHTML = '<div class="map-loading">데이터 없음</div>';
      return;
    }
    renderHeatmap(body, data.data);
  } catch(e) {
    body.innerHTML = '<div class="map-loading">오류 발생</div>';
  }
}

function renderHeatmap(container, stocks) {
  // color scale: -3% ~ +3%
  function pctToColor(pct) {
    if (pct >= 3)   return { bg: "#1A3A2A", text: "#4ADE80", border: "#166534" };
    if (pct >= 1.5) return { bg: "#162E22", text: "#22D3EE", border: "#155E75" };
    if (pct >= 0.3) return { bg: "#112832", text: "#67E8F9", border: "#155E75" };
    if (pct >= -0.3)return { bg: "#1A1F2E", text: "#94A3B8", border: "#334155" };
    if (pct >= -1.5)return { bg: "#2A1622", text: "#F9A8D4", border: "#9F1239" };
    if (pct >= -3)  return { bg: "#301218", text: "#FB7185", border: "#881337" };
    return              { bg: "#3B0A12", text: "#F43F5E", border: "#9F1239" };
  }

  const cells = stocks.map(s => {
    const c = pctToColor(s.change_pct);
    const sign = s.change_pct >= 0 ? "+" : "";
    return `<div class="hm-cell" style="background:${c.bg};border-color:${c.border}"
                 onclick="goAnalyze('${s.ticker}')" title="${s.name}: ${sign}${s.change_pct}%">
      <div class="hm-short" style="color:${c.text}">${s.short}</div>
      <div class="hm-pct"   style="color:${c.text}">${sign}${s.change_pct.toFixed(1)}%</div>
    </div>`;
  }).join("");

  container.innerHTML = `<div class="hm-grid">${cells}</div>`;
}

// ── 52주 신고가 ───────────────────────────────────────
let _current52Market = "kospi";

async function load52h(market, btn) {
  _current52Market = market;
  document.querySelectorAll(".h52-tab").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");

  const grid = document.getElementById("high52Grid");
  grid.innerHTML = '<div class="high52-loading">조회 중…</div>';

  try {
    const data = await fetch(`/api/market/52h/${market}`).then(r => r.json());
    if (!data.ok || !data.data.length) {
      grid.innerHTML = '<div class="high52-empty">해당 시장에서 52주 신고가 종목이 없습니다.</div>';
      return;
    }
    render52hGrid(grid, data.data);
  } catch(e) {
    grid.innerHTML = '<div class="high52-empty">오류가 발생했습니다.</div>';
  }
}

function render52hGrid(grid, stocks) {
  const cards = stocks.map(s => {
    const dayCls  = s.day_pct  >= 0 ? "bull" : "bear";
    const daySign = s.day_pct  >= 0 ? "+" : "";
    const gapCls  = s.gap_pct  >= 0 ? "bull" : "bear";
    const gapSign = s.gap_pct  >= 0 ? "+" : "";
    // streak badge color
    const strColor = s.streak >= 8 ? "#F59E0B" : s.streak >= 4 ? "#818CF8" : "#22D3EE";
    return `
      <div class="h52-card" onclick="goAnalyze('${s.ticker}')">
        <div class="h52-top">
          <div>
            <div class="h52-name">${s.name}</div>
            <div class="h52-ticker">${s.ticker}</div>
          </div>
          <div class="h52-streak" style="background:${strColor}22;color:${strColor};border-color:${strColor}55">
            ${s.streak}주 연속
          </div>
        </div>
        <div class="h52-price">${fmt(s.close)}</div>
        <div class="h52-meta">
          <div class="h52-meta-item">
            <span class="h52-meta-label">52주 고점</span>
            <span class="h52-meta-val">${fmt(s.high52)}</span>
          </div>
          <div class="h52-meta-item">
            <span class="h52-meta-label">고점 대비</span>
            <span class="h52-meta-val ${gapCls}">${gapSign}${s.gap_pct.toFixed(1)}%</span>
          </div>
          <div class="h52-meta-item">
            <span class="h52-meta-label">당일 등락</span>
            <span class="h52-meta-val ${dayCls}">${daySign}${s.day_pct.toFixed(2)}%</span>
          </div>
        </div>
      </div>`;
  }).join("");
  grid.innerHTML = `<div class="h52-cards">${cards}</div>`;
}

// ── 포트폴리오 ─────────────────────────────────────────
async function loadPortfolio() {
  const wrap = document.getElementById("portfolioWrap");
  if (!wrap) return;
  try {
    const data = await fetch("/api/portfolio").then(r => r.json());
    if (!data.ok) { renderEmptyPortfolio(wrap); return; }
    const { positions, summary } = data;
    if (!positions.length) { renderEmptyPortfolio(wrap); return; }
    renderPortfolio(wrap, positions, summary);
  } catch(e) { renderEmptyPortfolio(wrap); }
}

function renderEmptyPortfolio(wrap) {
  wrap.innerHTML = `
    <div class="portfolio-wrap">
      <div class="empty-portfolio">
        <div class="ep-icon">📭</div>
        <div class="ep-title">보유 종목이 없습니다</div>
        <div class="ep-sub">신규 진입 종목 찾기에서 종목을 추가해보세요</div>
        <a href="/scan" class="ep-scan-btn">신규 진입 종목 찾기 →</a>
      </div>
    </div>`;
}

function renderPortfolio(wrap, positions, summary) {
  const totalCls = summary.total_profit >= 0 ? "bull" : "bear";
  const rows = positions.map(p => {
    const pCls  = p.profit >= 0 ? "pt-bull" : "pt-bear";
    const sign  = p.profit >= 0 ? "+" : "";
    const dSign = p.day_change_pct >= 0 ? "+" : "";
    return `
      <tr>
        <td><div class="pt-name">${p.name}</div><div class="pt-ticker">${p.ticker}</div></td>
        <td>${p.quantity.toLocaleString("ko-KR")}</td>
        <td>${fmt(p.avg_price)}</td>
        <td>
          <div>${fmt(p.current_price)}</div>
          <div style="font-size:11px;color:${p.day_change_pct>=0?'var(--bull)':'var(--bear)'}">${dSign}${p.day_change_pct?.toFixed(2)}%</div>
        </td>
        <td>${fmt(p.value)}</td>
        <td class="${pCls}">${sign}${fmt(p.profit)}</td>
        <td class="${pCls}">${sign}${p.profit_pct.toFixed(2)}%</td>
        <td><button class="pt-btn pt-btn-analyze" onclick="goAnalyze('${p.ticker}')">분석</button></td>
      </tr>`;
  }).join("");

  wrap.innerHTML = `
    <div class="portfolio-wrap">
      <div class="portfolio-summary">
        <div class="ps-item"><div class="ps-label">총 투자금액</div><div class="ps-value">${fmt(summary.total_cost)}</div></div>
        <div class="ps-item"><div class="ps-label">총 평가금액</div><div class="ps-value">${fmt(summary.total_value)}</div></div>
        <div class="ps-item"><div class="ps-label">총 손익</div><div class="ps-value ${totalCls}">${summary.total_profit>=0?"+":""}${fmt(summary.total_profit)}</div></div>
        <div class="ps-item"><div class="ps-label">수익률</div><div class="ps-value ${totalCls}">${summary.total_profit>=0?"+":""}${summary.total_pct.toFixed(2)}%</div></div>
      </div>
      <div class="ptable-wrap">
        <table class="portfolio-table">
          <thead><tr>
            <th style="text-align:left">종목</th>
            <th>수량</th><th>평단가</th><th>현재가</th>
            <th>평가금액</th><th>손익</th><th>수익률</th><th></th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

// ── 초기화 ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadMarket();
  loadPortfolio();
  // 마켓맵은 지수 로드 후 순차적으로
  setTimeout(() => { loadMarketMap("KR"); loadMarketMap("US"); }, 1200);
  // 52주 신고가: 초기 탭 (KOSPI)
  load52h("kospi", document.querySelector(".h52-tab"));
});
