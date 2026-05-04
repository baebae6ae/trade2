/* static/js/analyze.js */

const COL_LABELS = {
  Date:"날짜", Open:"시가", High:"고가", Low:"저가", Close:"종가",
  Volume:"거래량", EMA20:"EMA20", EMA60:"EMA60", RSI14:"RSI(14)",
  MACD:"MACD", FIS:"FIS",
  ICH_TENKAN:"전환선", ICH_KIJUN:"기준선",
  ICH_SENKOU_A:"선행A", ICH_SENKOU_B:"선행B",
};

let _currentTicker = "";
let _currentName   = "";
let _currentPrice  = 0;

function rsiColor(v)  { return v>=70?"var(--bull)":v<=30?"var(--bear)":"var(--text2)"; }
function rsiStatus(v) { return v>=70?"과매수":v<=30?"과매도":"중립"; }
function rvolStatus(v){ return v>2?"급등":v>1.5?"증가":v>0.8?"보통":"감소"; }

function getTickerFromURL() {
  return (new URLSearchParams(window.location.search).get("ticker")||"").toUpperCase();
}
function reloadChart() {
  const t = getTickerFromURL();
  if (t) loadAnalysis(t);
}

// ── 메인 로드 ──────────────────────────────────────────────
async function loadAnalysis(ticker) {
  _currentTicker = ticker;
  const period = document.getElementById("periodSelect")?.value || "2y";
  document.getElementById("loadingOverlay").style.display = "flex";
  document.getElementById("analyzeMain").style.display    = "none";

  try {
    const data = await fetch(`/api/analyze/${ticker}?period=${period}&bars=220`)
                       .then(r => r.json());
    if (!data.ok) { showToast("오류: " + data.error, "error"); hideLoading(); return; }

    const info = data.info;
    _currentName  = info.name || ticker;
    _currentPrice = data.latest.close;

    // ── 종목 헤더 ─────────────────────────────────────
    document.getElementById("stockName").textContent     = _currentName;
    document.getElementById("stockTicker").textContent   = ticker;
    document.getElementById("stockExchange").textContent = info.exchange || "";
    document.getElementById("stockPrice").textContent    = fmt(_currentPrice);
    document.getElementById("stockCurrency").textContent = info.currency || "";
    document.getElementById("stockMeta").textContent     =
      [info.sector, info.industry].filter(Boolean).join(" · ");
    document.title = `CFIE — ${_currentName}`;

    const l = data.latest;
    const dayChgEl = document.getElementById("stockDayChg");
    const dSign = l.day_change_pct >= 0 ? "+" : "";
    dayChgEl.textContent  = `${dSign}${l.day_change_pct?.toFixed(2)}% (${dSign}${fmt(l.day_change_abs)})`;
    dayChgEl.className    = "sh-daychg " + (l.day_change_pct > 0 ? "bull" : l.day_change_pct < 0 ? "bear" : "flat");

    // ── FIS 배지 ──────────────────────────────────────
    const j   = data.judgment;
    const fis = j.fis;
    const col = fisColor(fis);

    document.getElementById("fisBadge").textContent  = `FIS ${fis>=0?"+":""}${fis.toFixed(1)}`;
    document.getElementById("fisBadge").style.background = col;
    document.getElementById("labelChip").textContent = j.label;
    document.getElementById("labelChip").style.background = col;

    // ── 판단 텍스트 ───────────────────────────────────
    document.getElementById("judgeL1").textContent    = j.summary_l1;
    document.getElementById("judgeL2").textContent    = j.summary_l2;
    document.getElementById("judgeExtra").textContent = j.extra || "";

    // ── 점수 바 ───────────────────────────────────────
    const SCORE_NAMES = {
      TrendScore:"추세", MomentumScore:"모멘텀", StructureScore:"구조",
      CompressionScore:"압축", VolumeScore:"거래량", RiskPenalty:"위험"
    };
    const MAX = 30;
    document.getElementById("scoreBars").innerHTML =
      Object.entries(j.scores).map(([k, v]) => {
        const pct   = Math.min(100, (Math.abs(v) / MAX) * 100);
        const isPos = v >= 0;
        const clr   = isPos ? "var(--bull)" : "var(--bear)";
        const left  = isPos ? "50%" : `${50 - pct/2}%`;
        const w     = `${pct/2}%`;
        const label = SCORE_NAMES[k] || k;
        return `
          <div class="score-bar-item">
            <span class="score-bar-label">${label}</span>
            <div class="score-bar-track">
              <div style="position:absolute;top:0;left:${left};width:${w};height:100%;background:${clr};border-radius:3px;"></div>
              <div style="position:absolute;top:-4px;left:50%;width:1px;height:14px;background:var(--text3);opacity:0.4;"></div>
            </div>
            <span class="score-bar-val" style="color:${clr}">${isPos?"+":""}${v.toFixed(1)}</span>
          </div>`;
      }).join("");

    // ── 진입 타이밍 점수 ──────────────────────────────
    renderEntryScore(data.entry_score, l);

    // ── 주요 지표 칩 ──────────────────────────────────
    renderChips(j, l);

    // ── 차트 + 테이블 ─────────────────────────────────
    document.getElementById("mainChart").src = `data:image/png;base64,${data.chart}`;
    buildTable(data.table);

    document.getElementById("loadingOverlay").style.display = "none";
    document.getElementById("analyzeMain").style.display    = "block";
  } catch(e) {
    console.error(e);
    showToast("네트워크 오류: " + e.message, "error");
    hideLoading();
  }
}

// ── 진입 타이밍 렌더 ────────────────────────────────────────
function renderEntryScore(score, l) {
  // 배지 색상
  const eCol = score >= 20 ? "#2ea043" : score >= 14 ? "#56d364" : score >= 8 ? "#d29922" : "#6e7681";
  const badge = document.getElementById("entryScoreBadge");
  badge.textContent       = `${score >= 0 ? "+" : ""}${score.toFixed(1)}`;
  badge.style.background  = eCol;

  // 상태 텍스트
  let status;
  if      (score >= 20) status = "✅ 최적 진입 타이밍 — 강세 추세 + 적정 눌림";
  else if (score >= 14) status = "🟡 양호한 진입 기회 — 추세 내 조정 완료 근접";
  else if (score >=  8) status = "⚠️ 진입 검토 가능 — 일부 조건 충족";
  else                  status = "❌ 진입 적기 아님 — 추가 눌림 또는 추세 개선 대기";
  document.getElementById("entryStatus").textContent = status;

  // 진입 세부 지표 4개
  const ema20GapPct = l.ema20_gap_pct ?? 0;
  const bbPos       = l.bb_pos        ?? 50;
  const pos52       = l.pos52         ?? 50;
  const pb5d        = l.pullback_5d   ?? 0;

  // EMA20 이격률: sweet spot -2 ~ +6%
  const emaBarPct = Math.min(100, Math.max(0, (ema20GapPct + 15) / 30 * 100));  // -15~+15 → 0~100
  const emaGood   = ema20GapPct >= -2 && ema20GapPct <= 6;
  const emaCol    = emaGood ? "#2ea043" : Math.abs(ema20GapPct) > 12 ? "#e53935" : "#d29922";
  const emaSign   = ema20GapPct >= 0 ? "+" : "";

  // BB 위치: sweet 30~60%
  const bbGood = bbPos >= 30 && bbPos <= 60;
  const bbCol  = bbGood ? "#2ea043" : bbPos > 85 ? "#e53935" : "#d29922";

  // 52주 위치: sweet 65~90%
  const p52Good = pos52 >= 65 && pos52 <= 90;
  const p52Col  = p52Good ? "#2ea043" : pos52 > 95 ? "#e53935" : "#d29922";

  // 5봉 조정폭: sweet 3~12%
  const pbGood = pb5d >= 3 && pb5d <= 12;
  const pbCol  = pbGood ? "#2ea043" : pb5d > 15 ? "#e53935" : "#d29922";
  const pb5Bar = Math.min(100, pb5d / 20 * 100);

  document.getElementById("entryMetrics").innerHTML = `
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">EMA20 이격률</span>
        <span class="em-value" style="color:${emaCol}">${emaSign}${ema20GapPct.toFixed(1)}%</span>
      </div>
      <div class="em-bar-track">
        <div class="sweet" style="left:${(15/30)*100}%;width:${(8/30)*100}%;background:rgba(46,160,67,0.15)"></div>
        <div class="em-bar-fill" style="width:${emaBarPct}%;background:${emaCol}"></div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: -2~+6% (EMA 근접 눌림)</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">BB 위치</span>
        <span class="em-value" style="color:${bbCol}">${bbPos.toFixed(0)}%</span>
      </div>
      <div class="em-bar-track">
        <div class="sweet" style="left:30%;width:30%;background:rgba(46,160,67,0.15)"></div>
        <div class="em-bar-fill" style="width:${bbPos}%;background:${bbCol}"></div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 30~60% (BB 중간 이하)</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">52주 위치</span>
        <span class="em-value" style="color:${p52Col}">${pos52.toFixed(0)}%</span>
      </div>
      <div class="em-bar-track">
        <div class="sweet" style="left:65%;width:25%;background:rgba(46,160,67,0.15)"></div>
        <div class="em-bar-fill" style="width:${pos52}%;background:${p52Col}"></div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 65~90% (추세권, 저항 여유)</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">5봉 조정폭</span>
        <span class="em-value" style="color:${pbCol}">${pb5d.toFixed(1)}%</span>
      </div>
      <div class="em-bar-track">
        <div class="sweet" style="left:15%;width:45%;background:rgba(46,160,67,0.15)"></div>
        <div class="em-bar-fill" style="width:${pb5Bar}%;background:${pbCol}"></div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 3~12% (적정 눌림)</div>
    </div>`;
}

// ── 지표 칩 렌더 ────────────────────────────────────────────
function renderChips(j, l) {
  const chips = [
    {
      label: "RSI(14)",
      value: l.rsi.toFixed(1),
      sub:   rsiStatus(l.rsi),
      color: rsiColor(l.rsi),
    },
    {
      label: "RVOL",
      value: l.rvol.toFixed(2) + "x",
      sub:   rvolStatus(l.rvol),
      color: l.rvol > 1.5 ? "var(--bull)" : "var(--text2)",
    },
    {
      label: "ATR(14)",
      value: fmt(l.atr),
      sub:   "변동폭",
      color: "var(--text2)",
    },
    {
      label: "일목",
      value: j.ichimoku_status.split("—")[0].trim(),
      sub:   (j.ichimoku_status.split("—")[1] || "").trim(),
      color: "var(--accent)",
    },
    {
      label: "BB 위치",
      value: (l.bb_pos ?? 50).toFixed(0) + "%",
      sub:   l.bb_pos >= 80 ? "상단 과열" : l.bb_pos <= 30 ? "하단 저평" : "중립",
      color: l.bb_pos >= 80 ? "var(--bear)" : l.bb_pos <= 30 ? "var(--bull)" : "var(--text2)",
    },
    {
      label: "52주 위치",
      value: (l.pos52 ?? 50).toFixed(0) + "%",
      sub:   l.pos52 >= 95 ? "고점 저항권" : l.pos52 >= 65 ? "추세 상위권" : "하위권",
      color: l.pos52 >= 95 ? "var(--bear)" : l.pos52 >= 65 ? "var(--bull)" : "var(--text2)",
    },
  ];

  document.getElementById("indicatorChips").innerHTML = chips.map(c => `
    <div class="chip">
      <span class="chip-label">${c.label}</span>
      <span class="chip-value" style="color:${c.color}">${c.value}</span>
      <span class="chip-sub">${c.sub}</span>
    </div>`).join("");
}

// ── 테이블 ─────────────────────────────────────────────────
function buildTable(rows) {
  if (!rows?.length) return;
  const cols = Object.keys(rows[0]);
  document.getElementById("tableHead").innerHTML =
    `<tr>${cols.map(c => `<th>${COL_LABELS[c] || c}</th>`).join("")}</tr>`;
  document.getElementById("tableBody").innerHTML =
    [...rows].reverse().map(row => `
      <tr>${cols.map(c => {
        const v = row[c];
        if (c === "Date")   return `<td>${v}</td>`;
        if (c === "Volume") return `<td>${fmtVol(v)}</td>`;
        if (c === "FIS") {
          const f = parseFloat(v);
          return `<td style="color:${f>=0?"var(--bull)":"var(--bear)"};font-weight:700">${f>=0?"+":""}${f.toFixed(1)}</td>`;
        }
        if (c === "RSI14") {
          const r = parseFloat(v);
          return `<td style="color:${rsiColor(r)}">${r.toFixed(1)}</td>`;
        }
        return `<td>${v != null ? fmt(v) : "—"}</td>`;
      }).join("")}</tr>`).join("");
}

function hideLoading() {
  document.getElementById("loadingOverlay").style.display = "none";
}

// ── 매수/매도 모달 ─────────────────────────────────────────
function openBuyModal() {
  document.getElementById("modalTitle").textContent      = "매수 등록";
  document.getElementById("modalSubTicker").textContent  = `${_currentName} (${_currentTicker})`;
  document.getElementById("modalPrice").value  = Math.round(_currentPrice);
  document.getElementById("modalQty").value    = 1;
  document.getElementById("modalSellSection").style.display = "none";
  document.getElementById("modalBuySection").style.display  = "";
  document.getElementById("tradeModal").style.display = "flex";
  document.getElementById("modalQty").focus();
}

function openSellModal(isFull) {
  if (isFull) {
    if (!confirm(`${_currentName} (${_currentTicker})\n전량 매도하시겠습니까?`)) return;
    submitSell(0);
    return;
  }
  document.getElementById("modalTitle").textContent      = "부분 매도";
  document.getElementById("modalSubTicker").textContent  = `${_currentName} (${_currentTicker})`;
  document.getElementById("modalSellSection").style.display = "";
  document.getElementById("modalBuySection").style.display  = "none";
  document.getElementById("tradeModal").style.display = "flex";
  document.getElementById("modalSellQty").value = 1;
  document.getElementById("modalSellQty").focus();
}

function closeTradeModal() {
  document.getElementById("tradeModal").style.display = "none";
}

async function confirmBuy() {
  const qty   = parseInt(document.getElementById("modalQty").value);
  const price = parseFloat(document.getElementById("modalPrice").value);
  if (!qty   || qty   < 1) { alert("수량을 입력하세요.");   return; }
  if (!price || price <= 0) { alert("매수가를 입력하세요."); return; }
  const res = await fetch("/api/portfolio/buy", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ticker: _currentTicker, name: _currentName, qty, price})
  }).then(r => r.json());
  closeTradeModal();
  if (res.ok) showToast(`${_currentName} ${qty}주 매수 등록 완료`);
  else        showToast("오류: " + res.error, "error");
}

async function confirmSell() {
  const qty = parseInt(document.getElementById("modalSellQty").value);
  if (!qty || qty < 1) { alert("매도 수량을 입력하세요."); return; }
  submitSell(qty);
}

async function submitSell(qty) {
  const res = await fetch("/api/portfolio/sell", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ticker: _currentTicker, qty})
  }).then(r => r.json());
  closeTradeModal();
  if (res.ok) showToast(res.sold_all ? `${_currentTicker} 전량 매도 완료` : `${_currentTicker} ${qty}주 매도 완료`);
  else        showToast("오류: " + res.error, "error");
}

document.addEventListener("DOMContentLoaded", () => {
  const t = getTickerFromURL();
  if (t) loadAnalysis(t); else window.location.href = "/";
  document.getElementById("tradeModal")?.addEventListener("click", e => {
    if (e.target.id === "tradeModal") closeTradeModal();
  });
});
