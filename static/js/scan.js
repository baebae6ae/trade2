/* static/js/scan.js */

let _market = "kospi";
let _scanning = false;

function selectMarket(market) {
  _market = market;
  document.querySelectorAll(".mtab").forEach(t => {
    t.classList.toggle("active", t.dataset.market === market);
  });
  document.getElementById("resultsSection").style.display = "none";
}

async function doScan() {
  if (_scanning) return;
  _scanning = true;
  const btn = document.getElementById("scanBtn");
  btn.disabled = true;
  btn.innerHTML = `<span class="spin"></span> 분석 중...`;
  document.getElementById("resultsSection").style.display = "none";
  const label = {kospi:"코스피", kosdaq:"코스닥", us:"미국"}[_market];
  document.getElementById("loadingMsg").textContent = `${label} 종목 분석 중... (최대 30초 소요)`;
  document.getElementById("loadingOverlay").style.display = "flex";

  try {
    const data = await fetch(`/api/scan/${_market}`).then(r => r.json());
    document.getElementById("loadingOverlay").style.display = "none";
    if (!data.ok) { showToast("스캔 오류: " + data.error, "error"); return; }
    renderResults(data.candidates, label);
  } catch(e) {
    document.getElementById("loadingOverlay").style.display = "none";
    showToast("네트워크 오류: " + e.message, "error");
  } finally {
    _scanning = false;
    btn.disabled = false;
    btn.innerHTML = "스캔 시작";
  }
}

function renderResults(candidates, label) {
  const section = document.getElementById("resultsSection");
  const countEl = document.getElementById("resultCount");
  const gridEl  = document.getElementById("candidatesGrid");
  countEl.textContent = candidates.length + "개";
  document.getElementById("resultLabel").textContent =
    `${label} 눌림목 진입 후보 (강한 추세 + 현재 쉬는 중 · 진입점수 높은 순)`;

  if (!candidates.length) {
    gridEl.innerHTML = `
      <div class="no-result" style="grid-column:1/-1">
        <div class="nr-icon">🔍</div>
        <div>현재 신규 진입 조건을 충족하는 종목이 없습니다.</div>
        <div style="margin-top:6px;font-size:12px;color:var(--text3)">시장 상황이 개선되면 다시 스캔해보세요.</div>
      </div>`;
    section.style.display = "block";
    return;
  }

  gridEl.innerHTML = candidates.map(c => {
    const col    = fisColorGlobal(c.fis);
    // entry_score 색상: 20+ 진한 녹, 12+ 연녹, 8+ 노랑
    const eScore = c.entry_score ?? 0;
    const eCol   = eScore >= 20 ? "#2ea043" : eScore >= 12 ? "#56d364" : "#d29922";
    const tCls   = c.trend >= 10 ? "pos" : "neg";
    const mCls   = c.momentum >= 5 ? "pos" : c.momentum < 0 ? "neg" : "";
    // EMA20 이격률 계산 (표시용)
    const gapPct = c.ema20_gap != null ? c.ema20_gap.toFixed(1) : "—";
    return `
      <div class="candidate-card">
        <div class="cc-top">
          <div>
            <div class="cc-name">${c.name}</div>
            <div class="cc-ticker">${c.ticker} · ${fmt(c.close)}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
            <div class="cc-fis-badge" style="background:${col}">FIS ${c.fis>=0?"+":""}${c.fis.toFixed(0)}</div>
            <div class="cc-fis-badge" style="background:${eCol};font-size:11px">진입점 ${eScore>=0?"+":""}${eScore.toFixed(0)}</div>
          </div>
        </div>
        <div class="cc-label" style="color:${col}">${c.label}</div>
        <div class="cc-summary">${c.summary_l1}</div>
        <div class="cc-scores">
          <span class="cs-chip ${tCls}" title="추세점수">추세 ${c.trend>=0?"+":""}${c.trend.toFixed(0)}</span>
          <span class="cs-chip ${mCls}" title="모멘텀 — 낮을수록 눌림">모멘텀 ${c.momentum>=0?"+":""}${c.momentum.toFixed(0)}</span>
          <span class="cs-chip pos" style="background:rgba(46,160,67,0.12);color:#56d364" title="진입 타이밍 점수">진입 ${eScore>=0?"+":""}${eScore.toFixed(0)}</span>
          <span class="cs-chip" title="일목균형표">${c.ichimoku.split("—")[0].trim()}</span>
        </div>
        <div class="cc-actions">
          <button class="cc-btn cc-btn-analyze" onclick="goAnalyze('${c.ticker}')">차트 분석</button>
          <button class="cc-btn cc-btn-buy" onclick="openScanBuyModal('${c.ticker}','${c.name}',${c.close})">신규 진입</button>
        </div>
      </div>`;
  }).join("");
  section.style.display = "block";
}

function fisColorGlobal(fis) {
  if (fis >= 70)  return "#D32F2F";
  if (fis >= 40)  return "#E57373";
  if (fis >= 10)  return "#F9A825";
  if (fis >= -20) return "#64B5F6";
  if (fis >= -50) return "#1565C0";
  return "#0D47A1";
}

// ── 매수 모달 ──────────────────────────────────────────
let _scanTicker = "", _scanName = "";

function openScanBuyModal(ticker, name, price) {
  _scanTicker = ticker;
  _scanName   = name;
  document.getElementById("scanModalSub").textContent = `${name} (${ticker})`;
  document.getElementById("scanModalPrice").value = Math.round(price);
  document.getElementById("scanModalQty").value   = 1;
  document.getElementById("scanBuyModal").style.display = "flex";
  document.getElementById("scanModalQty").focus();
}
function closeScanBuyModal() {
  document.getElementById("scanBuyModal").style.display = "none";
}
async function confirmScanBuy() {
  const qty   = parseInt(document.getElementById("scanModalQty").value);
  const price = parseFloat(document.getElementById("scanModalPrice").value);
  if (!qty || qty < 1)     { alert("수량을 입력하세요."); return; }
  if (!price || price <= 0){ alert("매수가를 입력하세요."); return; }
  try {
    const res = await fetch("/api/portfolio/buy", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ticker: _scanTicker, name: _scanName, qty, price})
    }).then(r => r.json());
    closeScanBuyModal();
    if (res.ok) showToast(`${_scanName} ${qty}주 매수 등록 완료`);
    else        showToast("오류: " + res.error, "error");
  } catch(e) { showToast("오류: " + e.message, "error"); }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("scanBuyModal")?.addEventListener("click", e => {
    if (e.target.id === "scanBuyModal") closeScanBuyModal();
  });
});
