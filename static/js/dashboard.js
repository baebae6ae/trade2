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

function _hmDescText(mode) {
  return mode === "sector"
    ? "섹터 평균 등락률 | 블록 크기 = 섹터 내 종목 수 | 색상: 초록(상승) / 빨강(하락)"
    : "개별 종목 당일 등락률 | 섹터별로 그룹화 | 블록 크기 균등 | 색상: 초록(상승) / 빨강(하락)";
}

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

  // 히트맵 기준 설명
  const hmDesc = document.createElement("div");
  hmDesc.className = "hm-desc";
  hmDesc.id = region + "HmDesc";
  hmDesc.textContent = _hmDescText(mode);
  body.appendChild(hmDesc);

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
    const descEl = body.querySelector(".hm-desc");
    if (descEl) descEl.textContent = _hmDescText(mode);
  }
}

// ── 52주 신고가 ───────────────────────────────────────
const _h52State = {
  market: "kospi",
  offset: 0,
  limit: 10,
  hasMore: false,
  loading: false,
  items: [],
};

function _update52hMoreButton() {
  const wrap = document.getElementById("high52MoreWrap");
  const btn = document.getElementById("high52MoreBtn");
  if (!wrap || !btn) return;
  if (_h52State.hasMore) {
    wrap.style.display = "flex";
    btn.disabled = false;
    btn.textContent = "자세히 보기";
  } else {
    wrap.style.display = "none";
  }
}

async function load52h(market, btn) {
  document.querySelectorAll(".h52-tab").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");

  _h52State.market = market;
  _h52State.offset = 0;
  _h52State.items = [];
  _h52State.hasMore = false;

  const grid = document.getElementById("high52Grid");
  grid.innerHTML = '<div class="high52-loading">조회 중…</div>';
  _update52hMoreButton();

  try {
    const data = await fetch(`/api/market/52h/${market}?offset=0&limit=${_h52State.limit}`).then(r => r.json());
    if (!data.ok) {
      grid.innerHTML = '<div class="high52-empty">오류가 발생했습니다.</div>';
      return;
    }

    _h52State.items = data.data || [];
    _h52State.offset = data.next_offset || _h52State.limit;
    _h52State.hasMore = !!data.has_more;

    if (!_h52State.items.length) {
      grid.innerHTML = '<div class="high52-empty">해당 시장에서 52주 신고가 종목이 없습니다.</div>';
      _update52hMoreButton();
      return;
    }

    render52hGrid(grid, _h52State.items);
    _update52hMoreButton();
  } catch(e) {
    grid.innerHTML = '<div class="high52-empty">오류가 발생했습니다.</div>';
    _update52hMoreButton();
  }
}

async function loadMore52h() {
  if (_h52State.loading || !_h52State.hasMore) return;
  _h52State.loading = true;
  const btn = document.getElementById("high52MoreBtn");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "불러오는 중...";
  }

  try {
    const url = `/api/market/52h/${_h52State.market}?offset=${_h52State.offset}&limit=${_h52State.limit}`;
    const data = await fetch(url).then(r => r.json());
    if (!data.ok) {
      throw new Error(data.error || "load failed");
    }

    const nextItems = data.data || [];
    _h52State.items = _h52State.items.concat(nextItems);
    _h52State.offset = data.next_offset || (_h52State.offset + _h52State.limit);
    _h52State.hasMore = !!data.has_more;

    const grid = document.getElementById("high52Grid");
    render52hGrid(grid, _h52State.items);
  } catch (e) {
    console.error("loadMore52h error", e);
  } finally {
    _h52State.loading = false;
    _update52hMoreButton();
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
      <div class="h52-card" onclick="goAnalyze('${s.ticker}')" role="button" tabindex="0" onkeydown="if(event.key==='Enter'){goAnalyze('${s.ticker}')}" title="${s.name} 분석 열기">
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
  grid.innerHTML = cards;
}

// ── 포트폴리오 ─────────────────────────────────────────
async function loadPortfolio() {
  const wrap = document.getElementById("portfolioWrap");
  if (!wrap) return;
  try {
    const data = await fetch("/api/portfolio?lite=1").then(r => r.json());
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
        <td>
          <div class="pt-actions">
            <button class="pt-btn pt-btn-analyze" onclick="goAnalyze('${p.ticker}')">분석</button>
            <button class="pt-btn pt-btn-buy" onclick="openDashTradeModal('buy','${p.ticker}','${p.name}',${p.current_price},${p.quantity})">추가매수</button>
            <button class="pt-btn pt-btn-sell" onclick="openDashTradeModal('sell','${p.ticker}','${p.name}',${p.current_price},${p.quantity})">매도</button>
          </div>
        </td>
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

// ── Dashboard Trade Modal ───────────────────────────
let _dashTrade = { type: "buy", ticker: "", name: "", currentPrice: 0, maxQty: 0 };

function _dashNum(v) { return Number(v || 0).toLocaleString("ko-KR"); }

function openDashTradeModal(type, ticker, name, currentPrice, maxQty) {
  _dashTrade = { type, ticker, name, currentPrice: Number(currentPrice || 0), maxQty: Number(maxQty || 0) };

  const modal = document.getElementById("dashTradeModal");
  const title = document.getElementById("dashTradeTitle");
  const sub = document.getElementById("dashTradeSub");
  const qty = document.getElementById("dashTradeQty");
  const priceRow = document.getElementById("dashTradePriceRow");
  const price = document.getElementById("dashTradePrice");
  const helper = document.getElementById("dashTradeHelper");
  const confirm = document.getElementById("dashTradeConfirm");

  if (!modal || !title || !sub || !qty || !priceRow || !price || !helper || !confirm) return;

  const isBuy = type === "buy";
  title.textContent = isBuy ? "추가 매수" : "매도";
  sub.textContent = `${name} (${ticker})`;
  qty.value = isBuy ? "1" : String(Math.max(1, Math.min(1, _dashTrade.maxQty)));
  price.value = String(Math.round(_dashTrade.currentPrice || 0));
  priceRow.style.display = isBuy ? "grid" : "none";
  helper.textContent = isBuy
    ? `현재가 기준: ${_dashNum(Math.round(_dashTrade.currentPrice || 0))}원`
    : `보유 수량: ${_dashNum(_dashTrade.maxQty)}주`;
  confirm.textContent = isBuy ? "매수 등록" : "매도 실행";

  modal.style.display = "flex";
  qty.focus();
}

function closeDashTradeModal() {
  const modal = document.getElementById("dashTradeModal");
  if (modal) modal.style.display = "none";
}

async function confirmDashTrade() {
  const qty = parseInt(document.getElementById("dashTradeQty")?.value || "0", 10);
  if (!qty || qty < 1) {
    showToast("유효한 수량을 입력하세요.", "error");
    return;
  }

  const isBuy = _dashTrade.type === "buy";
  if (!isBuy && qty > _dashTrade.maxQty) {
    showToast("보유 수량보다 많은 매도는 불가합니다.", "error");
    return;
  }

  try {
    let res;
    if (isBuy) {
      const price = parseFloat(document.getElementById("dashTradePrice")?.value || "0");
      if (!price || price <= 0) {
        showToast("유효한 매수가를 입력하세요.", "error");
        return;
      }
      res = await fetch("/api/portfolio/buy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: _dashTrade.ticker, name: _dashTrade.name, qty, price })
      }).then(r => r.json());
    } else {
      res = await fetch("/api/portfolio/sell", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: _dashTrade.ticker, qty })
      }).then(r => r.json());
    }

    if (!res.ok) {
      showToast("오류: " + (res.error || (isBuy ? "매수 실패" : "매도 실패")), "error");
      return;
    }

    showToast(`${_dashTrade.name} ${qty}주 ${isBuy ? "추가매수" : "매도"} 완료`);
    closeDashTradeModal();
    loadPortfolio();
  } catch (e) {
    showToast("오류: " + e.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("dashTradeModal")?.addEventListener("click", (e) => {
    if (e.target?.id === "dashTradeModal") closeDashTradeModal();
  });
});


