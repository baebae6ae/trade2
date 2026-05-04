/* static/js/mypage.js */

let _mpTicker = "", _mpName = "", _mpQty = 0;

async function loadMyPage() {
  try {
    const data = await fetch("/api/portfolio").then(r => r.json());
    if (!data.ok) { renderMpEmpty(); return; }
    if (!data.positions.length) { renderMpEmpty(); return; }
    renderMpSummary(data.summary);
    renderMpTable(data.positions);
  } catch(e) { renderMpEmpty(); }
}

function renderMpSummary(s) {
  const cls = s.total_profit >= 0 ? "bull" : "bear";
  const sign = s.total_profit >= 0 ? "+" : "";
  document.getElementById("mpTotalCost").textContent   = fmt(s.total_cost);
  document.getElementById("mpTotalValue").textContent  = fmt(s.total_value);
  const profEl = document.getElementById("mpTotalProfit");
  profEl.textContent  = sign + fmt(s.total_profit);
  profEl.className    = "mp-card-value " + cls;
  const pctEl = document.getElementById("mpTotalPct");
  pctEl.textContent   = sign + s.total_pct.toFixed(2) + "%";
  pctEl.className     = "mp-card-value " + cls;
}

function renderMpTable(positions) {
  const wrap = document.getElementById("mpTableWrap");
  const rows = positions.map(p => {
    const cls  = p.profit >= 0 ? "mp-bull" : "mp-bear";
    const sign = p.profit >= 0 ? "+" : "";
    const dSign = p.day_change_pct >= 0 ? "+" : "";
    const dCls  = p.day_change_pct >= 0 ? "var(--bull)" : "var(--bear)";
    return `
      <tr>
        <td>
          <div class="mp-name">${p.name}</div>
          <div class="mp-ticker">${p.ticker}</div>
        </td>
        <td>${p.quantity.toLocaleString("ko-KR")}주</td>
        <td>${fmt(p.avg_price)}</td>
        <td>
          <div>${fmt(p.current_price)}</div>
          <div style="font-size:11px;color:${dCls}">${dSign}${p.day_change_pct?.toFixed(2)}%</div>
        </td>
        <td>${fmt(p.value)}</td>
        <td class="${cls}">${sign}${fmt(p.profit)}</td>
        <td class="${cls}">${sign}${p.profit_pct.toFixed(2)}%</td>
        <td>
          <div class="mp-actions">
            <button class="mp-btn mp-btn-analyze" onclick="goAnalyze('${p.ticker}')">분석</button>
            <button class="mp-btn mp-btn-buy" onclick="openMpBuyModal('${p.ticker}','${p.name}',${p.current_price})">추가매수</button>
            <button class="mp-btn mp-btn-sell" onclick="openMpSellModal('${p.ticker}','${p.name}',${p.quantity})">매도</button>
          </div>
        </td>
      </tr>`;
  }).join("");

  wrap.innerHTML = `
    <div class="mp-table-wrap">
      <div class="mp-table-header">
        <span class="mp-table-title">보유 종목</span>
        <button class="mp-refresh-btn" onclick="loadMyPage()">↺ 새로고침</button>
      </div>
      <div style="overflow-x:auto">
        <table class="mp-table">
          <thead>
            <tr>
              <th style="text-align:left">종목</th>
              <th>수량</th><th>평단가</th><th>현재가</th>
              <th>평가금액</th><th>손익</th><th>수익률</th><th></th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function renderMpEmpty() {
  document.getElementById("mpSummarySection").style.display = "none";
  document.getElementById("mpTableWrap").innerHTML = `
    <div class="mp-empty">
      <div class="mp-empty-icon">📭</div>
      <div class="mp-empty-title">보유 종목이 없습니다</div>
      <div class="mp-empty-sub">신규 진입 종목 찾기에서 종목을 추가해보세요</div>
      <a href="/scan" class="ep-scan-btn">신규 진입 종목 찾기 →</a>
    </div>`;
}

// ── 추가 매수 모달 ─────────────────────────────────────
function openMpBuyModal(ticker, name, price) {
  _mpTicker = ticker; _mpName = name;
  document.getElementById("mpBuyModalSub").textContent = `${name} (${ticker})`;
  document.getElementById("mpBuyPrice").value = Math.round(price);
  document.getElementById("mpBuyQty").value   = 1;
  document.getElementById("mpBuyModal").style.display = "flex";
  document.getElementById("mpBuyQty").focus();
}
function closeMpBuyModal() { document.getElementById("mpBuyModal").style.display = "none"; }
async function confirmMpBuy() {
  const qty   = parseInt(document.getElementById("mpBuyQty").value);
  const price = parseFloat(document.getElementById("mpBuyPrice").value);
  if (!qty||qty<1)       { alert("수량을 입력하세요."); return; }
  if (!price||price<=0)  { alert("매수가를 입력하세요."); return; }
  const res = await fetch("/api/portfolio/buy", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ticker:_mpTicker, name:_mpName, qty, price})
  }).then(r=>r.json());
  closeMpBuyModal();
  if (res.ok) { showToast(`${_mpName} 추가 매수 완료`); loadMyPage(); }
  else        { showToast("오류: "+res.error, "error"); }
}

// ── 매도 모달 ──────────────────────────────────────────
function openMpSellModal(ticker, name, qty) {
  _mpTicker = ticker; _mpName = name; _mpQty = qty;
  document.getElementById("mpSellModalSub").textContent = `${name} (${ticker}) · 보유 ${qty.toLocaleString("ko-KR")}주`;
  document.getElementById("mpSellQty").value   = "";
  document.getElementById("mpSellModal").style.display = "flex";
  document.getElementById("mpSellQty").focus();
}
function closeMpSellModal() { document.getElementById("mpSellModal").style.display = "none"; }
async function confirmMpSell(isFull) {
  const qty = isFull ? 0 : parseInt(document.getElementById("mpSellQty").value);
  if (!isFull && (!qty||qty<1)) { alert("매도 수량을 입력하세요."); return; }
  const res = await fetch("/api/portfolio/sell", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ticker: _mpTicker, qty})
  }).then(r=>r.json());
  closeMpSellModal();
  if (res.ok) {
    const msg = res.sold_all ? `${_mpName} 전량 매도 완료` : `${_mpName} ${qty}주 매도 완료`;
    showToast(msg);
    loadMyPage();
  } else { showToast("오류: "+res.error, "error"); }
}

document.addEventListener("DOMContentLoaded", () => {
  loadMyPage();
  document.getElementById("mpBuyModal")?.addEventListener("click", e => { if (e.target.id==="mpBuyModal") closeMpBuyModal(); });
  document.getElementById("mpSellModal")?.addEventListener("click", e => { if (e.target.id==="mpSellModal") closeMpSellModal(); });
});
