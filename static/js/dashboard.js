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
    const abssign= (item.change||0) > 0 ? "+" : "";
    const arrow  = pct > 0 ? "▲" : pct < 0 ? "▼" : "—";
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
const _mapCache = {};   // region -> data
const _mapMode  = { KR: "sector", US: "sector" };

async function loadMarketMap(region) {
  const bodyId = region === "KR" ? "krMapBody" : "usMapBody";
  const body   = document.getElementById(bodyId);
  if (!body) return;

  if (_mapCache[region]) {
    _drawMap(region, body, _mapCache[region]);
    return;
  }
  body.innerHTML = '<div class="map-loading">히트맵 로딩 중…</div>';
  try {
    const data = await fetch(`/api/marketmap/${region}`).then(r => r.json());
    if (!data.ok || !data.data) {
      body.innerHTML = '<div class="map-loading">데이터 없음</div>';
      return;
    }
    _mapCache[region] = data.data;
    _drawMap(region, body, data.data);
  } catch(e) {
    body.innerHTML = '<div class="map-loading">오류 발생</div>';
  }
}

function _drawMap(region, body, data) {
  const mode = _mapMode[region] || "sector";
  body.innerHTML = "";

  // 탭 헤더
  const tabBar = document.createElement("div");
  tabBar.className = "hm-tabs";
  tabBar.innerHTML = `
    <button class="hm-tab ${mode==="sector"?"active":""}" onclick="_switchMapMode('${region}','sector',this)">섹터</button>
    <button class="hm-tab ${mode==="stock"?"active":""}"  onclick="_switchMapMode('${region}','stock',this)">종목</button>`;
  body.appendChild(tabBar);

  const canvas = document.createElement("div");
  canvas.className = "hm-canvas";
  body.appendChild(canvas);
  renderTreemap(canvas, data, mode);
}

function _switchMapMode(region, mode, btn) {
  _mapMode[region] = mode;
  btn.closest(".ms-map-body").querySelectorAll(".hm-tab").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  if (_mapCache[region]) {
    const bodyId = region === "KR" ? "krMapBody" : "usMapBody";
    const body   = document.getElementById(bodyId);
    const canvas = body.querySelector(".hm-canvas");
    if (canvas) {
      canvas.innerHTML = "";
      renderTreemap(canvas, _mapCache[region], mode);
    }
  }
}

// ── 52주 신고가 ───────────────────────────────────────
async function load52h(market, btn) {
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
  // 우선순위 1: 지수 + 포트폴리오 (빠름)
  loadMarket();
  loadPortfolio();
  // 우선순위 2: 마켓맵 (배치 다운로드, 10~20초 소요 예상)
  setTimeout(() => loadMarketMap("KR"), 800);
  setTimeout(() => loadMarketMap("US"), 900);
  // 우선순위 3: 52주 신고가 (배치, 느림)
  setTimeout(() => load52h("kospi", document.querySelector(".h52-tab")), 1000);
});
