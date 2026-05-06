/* static/js/mypage.js */

let _mpTicker = "", _mpName = "", _mpQty = 0;

async function loadMyPage() {
  try {
    const data = await fetch("/api/portfolio").then(r => r.json());
    if (!data.ok) { renderMpEmpty(); return; }
    if (!data.positions.length) { renderMpEmpty(); return; }
    renderMpSummary(data.summary);
    renderMpAnalysis(data.analysis);
    renderMpTable(data.positions);
  } catch(e) { renderMpEmpty(); }
}

function fisColor(fis) {
  if (fis >= 65) return "#D32F2F";
  if (fis >= 30) return "#E57373";
  if (fis >= 5)  return "#F9A825";
  if (fis >= -20) return "#64B5F6";
  if (fis >= -50) return "#1565C0";
  return "#0D47A1";
}

function entryColor(score) {
  if (score >= 80) return "#2ea043";
  if (score >= 65) return "#56d364";
  if (score >= 50) return "#d29922";
  return "#6e7681";
}

function renderMpAnalysis(analysis) {
  const box = document.getElementById("mpAnalysisSection");
  if (!analysis) {
    box.style.display = "none";
    return;
  }
  const fisCls = analysis.weighted_fis >= 0 ? "bull" : "bear";
  const entryCls = analysis.weighted_entry_score >= 65 ? "bull" : analysis.weighted_entry_score < 50 ? "bear" : "";
  const riskCls = analysis.weighted_risk >= -8 ? "bull" : "bear";
  box.innerHTML = `
    <div class="mp-analysis-head">
      <div>
        <div class="mp-analysis-title">내 포트폴리오 분석</div>
        <div class="mp-analysis-sub">보유 종목의 FIS, 진입 점수, 위험 감점, 비중 집중도를 합산해 포트폴리오 자체의 현재 상태를 판단합니다.</div>
      </div>
      <div class="mp-analysis-badge" style="background:${analysis.label_color}">${analysis.label}</div>
    </div>
    <div class="mp-analysis-grid">
      <div class="mp-analysis-card">
        <div class="mp-analysis-label">가중 FIS</div>
        <div class="mp-analysis-value ${fisCls}">${analysis.weighted_fis >= 0 ? "+" : ""}${analysis.weighted_fis.toFixed(1)}</div>
        <div class="mp-analysis-note">보유 비중 반영 전체 차트 우위</div>
      </div>
      <div class="mp-analysis-card">
        <div class="mp-analysis-label">가중 진입 점수</div>
        <div class="mp-analysis-value ${entryCls}">${analysis.weighted_entry_score.toFixed(1)}</div>
        <div class="mp-analysis-note">추가 매수 타이밍 평균 질</div>
      </div>
      <div class="mp-analysis-card">
        <div class="mp-analysis-label">가중 위험 감점</div>
        <div class="mp-analysis-value ${riskCls}">${analysis.weighted_risk.toFixed(1)}</div>
        <div class="mp-analysis-note">낮을수록 과열/매물 부담이 큼</div>
      </div>
      <div class="mp-analysis-card">
        <div class="mp-analysis-label">분산도</div>
        <div class="mp-analysis-value">${analysis.diversification_score.toFixed(1)}</div>
        <div class="mp-analysis-note">낮을수록 특정 종목 비중 집중</div>
      </div>
    </div>
    <div class="mp-analysis-points">
      <div class="mp-analysis-point">${analysis.summary_l1}</div>
      <div class="mp-analysis-point">${analysis.summary_l2}</div>
      <div class="mp-analysis-point">가장 강한 종목: ${analysis.strongest_name} / 가장 약한 종목: ${analysis.weakest_name}</div>
    </div>`;
  box.style.display = "block";
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
          <div class="mp-signal-row">
            <span class="mp-signal" style="background:${fisColor(p.fis || 0)}22;color:${fisColor(p.fis || 0)};border-color:${fisColor(p.fis || 0)}55">FIS ${(p.fis || 0) >= 0 ? "+" : ""}${(p.fis || 0).toFixed(0)}</span>
            <span class="mp-signal" style="background:${entryColor(p.entry_score || 0)}22;color:${entryColor(p.entry_score || 0)};border-color:${entryColor(p.entry_score || 0)}55">진입 점수 ${(p.entry_score || 0).toFixed(0)}</span>
            <span class="mp-signal mp-signal-risk">위험 ${(p.risk || 0).toFixed(0)}</span>
          </div>
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
  document.getElementById("mpAnalysisSection").style.display = "none";
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
