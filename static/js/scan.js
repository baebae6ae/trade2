/* static/js/scan.js */
let _scanType = "fis";

function selectScanType(type) {
  _scanType = type;
  document.querySelectorAll(".stab").forEach(t => {
    t.classList.toggle("active", t.dataset.type === type);
  });
  const desc = document.getElementById("kumoDesc");
  if (desc) desc.style.display = type === "kumo" ? "block" : "none";
  document.getElementById("resultsSection").style.display = "none";
}


let _market = "kospi";
let _scanning = false;
let _scanCandidates = [];

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
  const scanLabel = _scanType === "kumo" ? "쿠모 브레이크아웃" : "FIS 진입";
  document.getElementById("loadingMsg").textContent = `${label} ${scanLabel} 분석 중... (최대 30초 소요)`;
  document.getElementById("loadingOverlay").style.display = "flex";

  try {
    const apiUrl = _scanType === "kumo"
      ? `/api/scan/kumo/${_market}`
      : `/api/scan/${_market}`;
    const data = await fetch(apiUrl).then(r => r.json());
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
  _scanCandidates = candidates;
  const section = document.getElementById("resultsSection");
  const countEl = document.getElementById("resultCount");
  const gridEl  = document.getElementById("candidatesGrid");
  countEl.textContent = candidates.length + "개";
  const resultDesc = _scanType === "kumo"
    ? `${label} 쿠모 브레이크아웃 패턴 종목 (구름 아래 체류기간 긴 순)`
    : `${label} 상승 우위 진입 후보 (진입 점수 높은 순)`;
  document.getElementById("resultLabel").textContent = resultDesc;

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

  if (_scanType === "kumo") {
    gridEl.innerHTML = candidates.map(c => renderKumoCard(c)).join("");
    section.style.display = "block";
    return;
  }
  gridEl.innerHTML = candidates.map((c, idx) => {
    const col    = fisColorGlobal(c.fis);
    const eScore = c.entry_score ?? 0;
    const eCol   = eScore >= 80 ? "#2ea043" : eScore >= 65 ? "#56d364" : eScore >= 50 ? "#d29922" : "#6e7681";
    const tCls   = c.trend >= 10 ? "pos" : "neg";
    const mCls   = c.momentum >= 5 ? "pos" : c.momentum < 0 ? "neg" : "";
    return `
      <div class="candidate-card">
        <div class="cc-top">
          <div>
            <div class="cc-name">${c.name}</div>
            <div class="cc-ticker">${c.ticker} · ${fmt(c.close)}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
            <div class="cc-fis-badge" style="background:${col}">FIS ${c.fis>=0?"+":""}${c.fis.toFixed(0)}</div>
            <div class="cc-fis-badge" style="background:${eCol};font-size:11px">진입 점수 ${eScore.toFixed(0)}</div>
          </div>
        </div>
        <div class="cc-label" style="color:${col}">${c.label}</div>
        <div class="cc-summary">${c.summary_l1}</div>
        <div class="cc-scores">
          <span class="cs-chip ${tCls}" title="추세점수">추세 ${c.trend>=0?"+":""}${c.trend.toFixed(0)}</span>
          <span class="cs-chip ${mCls}" title="모멘텀">모멘텀 ${c.momentum>=0?"+":""}${c.momentum.toFixed(0)}</span>
          <span class="cs-chip" style="background:rgba(46,160,67,0.12);color:#56d364" title="진입 점수">진입 ${eScore.toFixed(0)}</span>
          <span class="cs-chip" title="일목균형표">${c.ichimoku.split("—")[0].trim()}</span>
        </div>
        <div class="cc-actions">
          <button class="cc-btn cc-btn-analyze" onclick="openChartModal(${idx})">차트 분석</button>
          <button class="cc-btn cc-btn-buy" onclick="openScanBuyModal('${c.ticker}','${c.name}',${c.close})">신규 진입</button>
        </div>
        <button class="det-toggle" id="det-btn-${idx}" onclick="toggleDetail(${idx})">▶ 상세 설명</button>
        <div class="det-body" id="det-${idx}">
          ${entryDetailHTML(c)}
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

// ── 상세 설명 ─────────────────────────────────────────────
function entryDetailHTML(c) {
  const comp   = c.entry_components    || {};
  const setups = c.entry_setup_scores  || {};
  const met    = c.entry_metrics       || {};
  const sName  = c.entry_setup_name    || "—";
  const sName2 = c.entry_setup_name2   || "";

  const ctx      = comp["추세문맥"]   ?? 0;
  const setup    = comp["진입구조"]   ?? 0;
  const trigger  = comp["확인신호"]   ?? 0;
  const space    = comp["저항여유"]   ?? 0;
  const riskCtrl = comp["리스크관리"] ?? 0;

  function sc(v, max) {
    const r = max > 0 ? v / max : 0;
    return r >= 0.7 ? "#2ea043" : r >= 0.4 ? "#d29922" : "#6e7681";
  }

  const ctxDesc =
    ctx >= 24 ? "FIS 강세·추세·ADX 모두 우세. 매수 환경이 충분히 갖춰진 상태."
  : ctx >= 16 ? "추세 환경 양호. 방향성 우위 확인됨."
  : ctx >= 8  ? "추세 환경 중립 이상. 조건부 진입 가능."
  :             "추세 뒷받침 부족. 신중한 접근 필요.";

  const setupDescs = {
    "추세 눌림":  "상승 흐름 속 조정 후 재진입 시도. EMA 근접 눌림 + RSI 과열 해소가 핵심.",
    "압축 돌파":  "좁은 횡보에 에너지 압축 후 거래량 동반 상단 돌파 시도.",
    "모멘텀 지속": "정배열(EMA10>20>60) 상승 중인 추세에서 지속 진입. 강한 ROC·거래량 확인.",
    "반전 초기":  "과매도 후 바닥 반전 초기 신호. MACD 반전·RSI 저점 반등 확인."
  };

  const trigDesc =
    trigger >= 18 ? "EMA 배열·MACD·거래량 신호 모두 동반. 진입 타이밍 강."
  : trigger >= 12 ? "핵심 진입 신호 대부분 확인됨."
  : trigger >= 6  ? "일부 신호만 충족. 추가 봉 확인 권장."
  :                 "명확한 진입 신호 아직 부족.";

  const spaceDesc =
    space >= 12 ? "52주 위치·BB 모두 상승 여유 충분. 상단 저항 부담 낮음."
  : space >= 6  ? "적정한 상승 공간 확인됨."
  : space >= 0  ? "일부 저항 부담 있음. 상단 확인 필요."
  :               "상단 저항 과부담. 추격 매수 불리.";

  const riskDesc =
    riskCtrl >= 12 ? "과열 없고 손절가 거리 적정. 위험 관리 조건 양호."
  : riskCtrl >= 8  ? "리스크 통제 가능 수준."
  : riskCtrl >= 4  ? "일부 위험 요소 있음. 손절선 명확히 설정 권장."
  :                  "ATR 대비 이격 크거나 위험 감점 높음. 주의 필요.";

  const setupChips = Object.entries(setups).map(([k, v]) =>
    `<span class="det-setup-chip${k === sName ? " best" : ""}">${k} ${v.toFixed(0)}점${k === sName ? " ★" : ""}</span>`
  ).join("");

  const rows = [
    { label: "① 추세문맥",             v: ctx,      max: 30, desc: ctxDesc },
    { label: `② 진입구조 — ${sName}${sName2 ? ` + ${sName2}` : ""}`,  v: setup,    max: 30, desc: setupDescs[sName] || "—", extra: setupChips },
    { label: "③ 확인신호",             v: trigger,  max: 24, desc: trigDesc },
    { label: "④ 저항여유",             v: space,    max: 18, desc: spaceDesc },
    { label: "⑤ 리스크관리",           v: riskCtrl, max: 16, desc: riskDesc },
  ];

  const compsHTML = rows.map(r => `
    <div class="det-comp">
      <div class="det-comp-hd">
        <span class="det-comp-label">${r.label}</span>
        <span class="det-comp-score" style="color:${sc(r.v, r.max)}">${r.v.toFixed(0)} / ${r.max}</span>
      </div>
      <div class="det-comp-desc">${r.desc}</div>
      ${r.extra ? `<div class="det-setup-chips">${r.extra}</div>` : ""}
    </div>`).join("");

  const gapPct = met.ema20_gap_pct != null
    ? (met.ema20_gap_pct >= 0 ? "+" : "") + met.ema20_gap_pct.toFixed(1) + "%" : "—";

  return compsHTML + `
    <div class="det-metrics">
      <span>EMA20 이격 ${gapPct}</span>
      <span>RSI ${met.rsi_reset != null ? met.rsi_reset.toFixed(1) : "—"}</span>
      <span>52주 ${met.range_pos != null ? met.range_pos.toFixed(0) + "%" : "—"}</span>
      <span>BB ${met.bb_pos != null ? met.bb_pos.toFixed(0) + "%" : "—"}</span>
      <span>ADX ${met.adx != null ? met.adx.toFixed(1) : "—"}</span>
    </div>`;
}

function toggleDetail(idx) {
  const body = document.getElementById(`det-${idx}`);
  const btn  = document.getElementById(`det-btn-${idx}`);
  if (!body) return;
  const open = body.style.display === "block";
  body.style.display = open ? "none" : "block";
  btn.textContent = open ? "▶ 상세 설명" : "▼ 상세 설명 닫기";
}

// ── 차트 분석 모달 ─────────────────────────────────────────
async function openChartModal(idx) {
  const c = _scanCandidates[idx];
  if (!c) return;
  document.getElementById("chartModalTitle").textContent  = c.name;
  document.getElementById("chartModalTicker").textContent = `${c.ticker} · ${fmt(c.close)}`;
  document.getElementById("chartModalFullLink").href      = `/analyze?ticker=${encodeURIComponent(c.ticker)}`;
  document.getElementById("chartModalBody").innerHTML = `
    <div style="text-align:center;padding:40px">
      <div class="spinner" style="margin:0 auto"></div>
      <p style="margin-top:16px;color:var(--text2);font-size:13px">차트 분석 중…</p>
    </div>`;
  document.getElementById("chartModal").style.display = "flex";
  try {
    const d = await fetch(
      `/api/analyze/${encodeURIComponent(c.ticker)}?period=2y&timeframe=daily&bars=220`
    ).then(r => r.json());
    if (!d.ok) {
      document.getElementById("chartModalBody").innerHTML =
        `<p style="color:var(--bear);padding:24px;text-align:center">분석 오류: ${d.error || "알 수 없는 오류"}</p>`;
      return;
    }
    const j = d.judgment;
    const l = d.latest;
    const eScore = d.entry?.score ?? 0;
    const eCol   = eScore >= 80 ? "#2ea043" : eScore >= 65 ? "#56d364" : eScore >= 50 ? "#d29922" : "#6e7681";
    const fCol   = fisColor(l.fis);
    const sign   = l.day_change_pct >= 0 ? "+" : "";
    const chgCol = l.day_change_pct >= 0 ? "var(--bull)" : "var(--bear)";
    document.getElementById("chartModalBody").innerHTML = `
      <div class="cmo-stat-row">
        <span class="cmo-badge" style="background:${fCol}">FIS ${l.fis >= 0 ? "+" : ""}${l.fis.toFixed(1)}</span>
        <span class="cmo-badge" style="background:${eCol}">진입 점수 ${eScore.toFixed(0)}</span>
        <span style="font-size:13px;font-weight:700;color:${fCol}">${j.label}</span>
        <span style="font-size:13px;color:var(--text1);margin-left:auto">${fmt(l.close)} <span style="color:${chgCol}">${sign}${l.day_change_pct.toFixed(2)}%</span></span>
      </div>
      <img src="data:image/png;base64,${d.chart}" class="cmo-chart-img">
      <div class="cmo-summary">${j.summary_l1}</div>
      ${j.summary_l2 ? `<div class="cmo-summary2">${j.summary_l2}</div>` : ""}`;
  } catch(e) {
    document.getElementById("chartModalBody").innerHTML =
      `<p style="color:var(--bear);padding:24px;text-align:center">분석 실패: ${e.message}</p>`;
  }
}

function closeChartModal() {
  document.getElementById("chartModal").style.display = "none";
}

// ── 매수 모달 ──────────────────────────────────────────
let _scanTicker = "", _scanName = "", _scanATR = 0, _scanHigh20 = 0;

function _fmtP2(v) { return (Math.round(v)||0).toLocaleString("ko-KR"); }
function _pct2(t, e) { const p=(t-e)/e*100; return (p>=0?"+":"")+p.toFixed(1)+"%"; }

function onScanQtyChange() {
  const qty   = parseInt(document.getElementById("scanModalQty").value)   || 1;
  const price = parseFloat(document.getElementById("scanModalPrice").value) || 0;
  document.getElementById("scanInvest").textContent = price ? _fmtP2(price * qty) + "원" : "—";
}
function onScanPriceChange() {
  const qty   = parseInt(document.getElementById("scanModalQty").value)   || 1;
  const price = parseFloat(document.getElementById("scanModalPrice").value) || 0;
  document.getElementById("scanInvest").textContent = price ? _fmtP2(price * qty) + "원" : "—";
}

function openScanBuyModal(ticker, name, price) {
  const c = _scanCandidates.find(x => x.ticker === ticker) || {};
  _scanTicker = ticker;
  _scanName   = name;
  _scanATR    = c.atr || 0;
  _scanHigh20 = c.high20 || 0;
  const entry = Math.round(price);
  const ts    = _scanHigh20 > 0 ? Math.round(_scanHigh20 - _scanATR * 2) : 0;
  const ema20 = parseFloat(c.entry_metrics?.ema20 || 0) || 0;

  document.getElementById("scanModalSub").textContent      = `${name} (${ticker})`;
  document.getElementById("scanModalScenario").textContent = c.entry_setup_name || "분석";
  document.getElementById("scanModalPrice").value          = entry;
  document.getElementById("scanModalQty").value            = 1;
  document.getElementById("scanInvest").textContent        = _fmtP2(entry) + "원";
  document.getElementById("scanTrailingStop").textContent  = ts > 0 ? _fmtP2(ts) : "—";
  document.getElementById("scanTrailingPct").textContent   = ts > 0 ? _pct2(ts, entry) : "";
  document.getElementById("scanEMA20").textContent         = ema20 > 0 ? _fmtP2(ema20) : "—";
  document.getElementById("scanEMASignal").textContent     = ema20 > 0
    ? (entry >= ema20 ? "✓ 상회" : "⬇ 하회 중") : "";
  document.getElementById("scanBuyModal").style.display    = "flex";
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
    if (res.ok) showToast(`${_scanName} ${qty}주 진입 등록 완료`);
    else        showToast("오류: " + res.error, "error");
  } catch(e) { showToast("오류: " + e.message, "error"); }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("scanBuyModal")?.addEventListener("click", e => {
    if (e.target.id === "scanBuyModal") closeScanBuyModal();
  });
  document.getElementById("chartModal")?.addEventListener("click", e => {
    if (e.target.id === "chartModal") closeChartModal();
  });
});



// ── 쿠모 브레이크아웃 카드 렌더 ──────────────────────────
function renderKumoCard(c) {
  const fmt2 = v => v >= 1000 ? v.toLocaleString() : v.toFixed(2);
  const cloudBadge = c.bull_cloud
    ? `<span style="background:#E53935;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700">상승구름</span>`
    : `<span style="background:#2196F3;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700">구름위</span>`;
  const volBadge = c.daily_vol
    ? `<span style="background:#2ea043;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700">거래량 폭발</span>`
    : `<span style="background:var(--bg3);color:var(--text2);padding:2px 8px;border-radius:12px;font-size:11px;">일봉 확인필요</span>`;
  return `
    <div class="candidate-card" onclick="openChartModal('${c.ticker}','${c.name}')">
      <div class="cc-top">
        <div>
          <div class="cc-name">${c.name}</div>
          <div class="cc-ticker">${c.ticker} · ${fmt(c.close)}</div>
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
          ${cloudBadge}
          ${volBadge}
        </div>
      </div>
      <div class="cc-scores" style="margin-top:10px">
        <span class="cs-chip pos" title="구름 아래 체류 주수">구름아래 ${c.below_weeks}주</span>
        <span class="cs-chip" style="background:var(--bg3);color:var(--text1)" title="구름 최소 두께">구름두께 ${c.cloud_thin}%</span>
      </div>
      <div style="margin-top:8px;font-size:11px;color:var(--text2)">
        주봉 구름 아래 <strong style="color:var(--text1)">${c.below_weeks}주</strong> 체류 후 상향 돌파 · 구름 반전 확인
      </div>
    </div>`;
}
