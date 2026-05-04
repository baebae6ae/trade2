/* static/js/dashboard.js */

// ── 시장 데이터 로드 ───────────────────────────────
async function loadMarket() {
  try {
    const data = await fetch("/api/market").then(r => r.json());
    if (!data.ok) return;
    renderTickerStrip(data.data);
    renderIndexCards("krGrid", data.data.KR);
    renderIndexCards("usGrid", data.data.US);
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
    return `
      <div class="ticker-item">
        <span class="ti-emoji">${item.emoji||""}</span>
        <span class="ti-name">${item.name}</span>
        <span class="ti-price">${item.price != null ? fmt(item.price) : "—"}</span>
        <span class="ti-chg ${cls}">${pct != null ? sign+pct.toFixed(2)+"%" : "—"}</span>
      </div>`;
  }).join("");
  track.innerHTML = html + html;   // 무한 스크롤을 위해 2배 복제
}

function renderIndexCards(gridId, items) {
  const grid = document.getElementById(gridId);
  if (!grid) return;
  grid.innerHTML = (items || []).map(item => {
    const pct = item.change_pct;
    const cls = pct > 0 ? "bull" : pct < 0 ? "bear" : "flat";
    const sign = pct > 0 ? "+" : "";
    const absSign = item.change > 0 ? "+" : "";
    return `
      <div class="index-card ${cls}" onclick="goAnalyze('${item.ticker}')">
        <div class="ic-header">
          <span class="ti-emoji">${item.emoji||""}</span>
          <span class="ic-name">${item.name}</span>
        </div>
        <div class="ic-price">${item.price != null ? fmt(item.price) : "—"}</div>
        <div class="ic-footer">
          <span class="ic-change ${cls}">${pct != null ? sign+pct.toFixed(2)+"%" : "—"}</span>
          <span class="ic-abs">${item.change != null ? absSign+fmt(item.change) : ""}</span>
        </div>
      </div>`;
  }).join("");
}

// ── 포트폴리오 로드 ────────────────────────────────────
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
    const pCls = p.profit >= 0 ? "pt-bull" : "pt-bear";
    const sign  = p.profit >= 0 ? "+" : "";
    const dSign = p.day_change_pct >= 0 ? "+" : "";
    return `
      <tr>
        <td>
          <div class="pt-name">${p.name}</div>
          <div class="pt-ticker">${p.ticker}</div>
        </td>
        <td>${p.quantity.toLocaleString("ko-KR")}</td>
        <td>${fmt(p.avg_price)}</td>
        <td>
          <div>${fmt(p.current_price)}</div>
          <div style="font-size:11px;color:${p.day_change_pct>=0?'var(--bull)':'var(--bear)'}">${dSign}${p.day_change_pct?.toFixed(2)}%</div>
        </td>
        <td>${fmt(p.value)}</td>
        <td class="${pCls}">${sign}${fmt(p.profit)}</td>
        <td class="${pCls}">${sign}${p.profit_pct.toFixed(2)}%</td>
        <td>
          <button class="pt-btn pt-btn-analyze" onclick="goAnalyze('${p.ticker}')">분석</button>
        </td>
      </tr>`;
  }).join("");

  wrap.innerHTML = `
    <div class="portfolio-wrap">
      <div class="portfolio-summary">
        <div class="ps-item">
          <div class="ps-label">총 투자금액</div>
          <div class="ps-value">${fmt(summary.total_cost)}</div>
        </div>
        <div class="ps-item">
          <div class="ps-label">총 평가금액</div>
          <div class="ps-value">${fmt(summary.total_value)}</div>
        </div>
        <div class="ps-item">
          <div class="ps-label">총 손익</div>
          <div class="ps-value ${totalCls}">${summary.total_profit>=0?"+":""}${fmt(summary.total_profit)}</div>
        </div>
        <div class="ps-item">
          <div class="ps-label">수익률</div>
          <div class="ps-value ${totalCls}">${summary.total_profit>=0?"+":""}${summary.total_pct.toFixed(2)}%</div>
        </div>
      </div>
      <div class="ptable-wrap">
        <table class="portfolio-table">
          <thead>
            <tr>
              <th style="text-align:left">종목</th>
              <th>수량</th>
              <th>평단가</th>
              <th>현재가</th>
              <th>평가금액</th>
              <th>손익</th>
              <th>수익률</th>
              <th></th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

// ── 초기화 ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadMarket();
  loadPortfolio();
});
