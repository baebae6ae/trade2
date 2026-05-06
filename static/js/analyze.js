/* static/js/analyze.js */

const COL_LABELS = {
  function renderEntryScore(entry, l, rangeLabel) {
    const score = entry?.score ?? 0;
    const components = entry?.components || {};
    const setupName = entry?.setup_name || "일반";
    const setupScores = entry?.setup_scores || {};
    const context = components["추세문맥"] ?? 0;
    const structure = components["진입구조"] ?? 0;
    const confirm = components["확인신호"] ?? 0;
    const space = components["저항여유"] ?? 0;
    const riskControl = components["리스크관리"] ?? 0;

    const eCol = score >= 80 ? "#2ea043" : score >= 65 ? "#56d364" : score >= 50 ? "#d29922" : "#6e7681";
    const badge = document.getElementById("entryScoreBadge");
    badge.textContent       = `${score.toFixed(1)}`;
    badge.style.background  = eCol;

    let status;
    if      (score >= 80) status = `최적 진입 구간 — ${setupName} 시나리오 우세`;
    else if (score >= 65) status = `양호한 진입 구간 — ${setupName} 시나리오 유효`;
    else if (score >= 50) status = `조건부 진입 가능 — ${setupName} 확인 신호 추가 필요`;
    else                  status = `진입 대기 구간 — ${setupName} 확률 우위 부족`;
    document.getElementById("entryStatus").textContent = status;

    const ema20GapPct = l.ema20_gap_pct ?? 0;
    const ema20GapAtr = l.ema20_gap_atr ?? 0;
    const bbPos       = l.bb_pos        ?? 50;
    const pos52       = l.pos52         ?? 50;
    const pb5d        = l.pullback_5d   ?? 0;
    const rsiReset    = entry?.metrics?.rsi_reset ?? l.rsi ?? 50;
    const adx         = entry?.metrics?.adx ?? 0;

    const emaBarPct = Math.min(100, Math.max(0, (ema20GapPct + 15) / 30 * 100));
    const emaGood   = ema20GapPct >= -1 && ema20GapPct <= 4;
    const emaCol    = emaGood ? "#2ea043" : Math.abs(ema20GapPct) > 12 ? "#e53935" : "#d29922";
    const emaSign   = ema20GapPct >= 0 ? "+" : "";
    const bbGood = bbPos >= 35 && bbPos <= 75;
    const bbCol  = bbGood ? "#2ea043" : bbPos > 85 ? "#e53935" : "#d29922";
    const p52Good = pos52 >= 55 && pos52 <= 90;
    const p52Col  = p52Good ? "#2ea043" : pos52 > 95 ? "#e53935" : "#d29922";
    const pbGood = pb5d >= 3 && pb5d <= 12;
    const pbCol  = pbGood ? "#2ea043" : pb5d > 15 ? "#e53935" : "#d29922";
    const pb5Bar = Math.min(100, pb5d / 20 * 100);
    const atrGapCol = ema20GapAtr >= -0.5 && ema20GapAtr <= 1.2 ? "#2ea043" : Math.abs(ema20GapAtr) > 3 ? "#e53935" : "#d29922";
    const rsiCol = rsiReset >= 42 && rsiReset <= 60 ? "#2ea043" : rsiReset > 72 || rsiReset < 30 ? "#e53935" : "#d29922";
    const compColor = (value, goodCut) => value >= goodCut ? "#2ea043" : value < 0 ? "#e53935" : "#d29922";

    const setupRows = Object.entries(setupScores).map(([name, value]) => `
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">${name}</span>
          <span class="em-value" style="color:${name === setupName ? '#2ea043' : 'var(--text2)'}">${value.toFixed(1)}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">${name === setupName ? '현재 가장 우세한 진입 시나리오' : '보조 진입 시나리오'}</div>
      </div>`).join("");

    document.getElementById("entryMetrics").innerHTML = `
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">진입 구조</span>
          <span class="em-value" style="color:${eCol}">${setupName}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">눌림, 돌파, 지속, 반전 초기 중 가장 유리한 구조를 채택</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">추세 문맥</span>
          <span class="em-value" style="color:${compColor(context, 18)}">${context.toFixed(1)}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">FIS, 구조, ADX, 구름 위치를 함께 반영</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">진입 구조 점수</span>
          <span class="em-value" style="color:${compColor(structure, 18)}">${structure.toFixed(1)}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">현재 차트가 어떤 방식의 상승 진입에 유리한지 평가</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">확인 신호</span>
          <span class="em-value" style="color:${compColor(confirm, 14)}">${confirm.toFixed(1)}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">MACD, 종가 위치, 거래량, 기준선 회복 여부</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">저항 여유</span>
          <span class="em-value" style="color:${compColor(space, 10)}">${space.toFixed(1)}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">상단 저항과 과열 부담을 감점</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">리스크 관리</span>
          <span class="em-value" style="color:${compColor(riskControl, 10)}">${riskControl.toFixed(1)}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">위험 감점, 변동성, 과열 정도를 반영</div>
      </div>
      ${setupRows}
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">EMA20 이격률</span>
          <span class="em-value" style="color:${emaCol}">${emaSign}${ema20GapPct.toFixed(1)}%</span>
        </div>
        <div class="em-bar-track">
          <div class="sweet" style="left:${(15/30)*100}%;width:${(8/30)*100}%;background:rgba(46,160,67,0.15)"></div>
          <div class="em-bar-fill" style="width:${emaBarPct}%;background:${emaCol}"></div>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: -1~+4% (과열 아닌 근접 지지)</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">EMA20 ATR 이격</span>
          <span class="em-value" style="color:${atrGapCol}">${ema20GapAtr >= 0 ? '+' : ''}${ema20GapAtr.toFixed(2)} ATR</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: -0.5 ~ +1.2 ATR</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">BB 위치</span>
          <span class="em-value" style="color:${bbCol}">${bbPos.toFixed(0)}%</span>
        </div>
        <div class="em-bar-track">
          <div class="sweet" style="left:30%;width:45%;background:rgba(46,160,67,0.15)"></div>
          <div class="em-bar-fill" style="width:${bbPos}%;background:${bbCol}"></div>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 35~75% (재가속 구간)</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">${rangeLabel || '장기 위치'}</span>
          <span class="em-value" style="color:${p52Col}">${pos52.toFixed(0)}%</span>
        </div>
        <div class="em-bar-track">
          <div class="sweet" style="left:55%;width:35%;background:rgba(46,160,67,0.15)"></div>
          <div class="em-bar-fill" style="width:${pos52}%;background:${p52Col}"></div>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 55~90% (상승 여유와 저항 균형)</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">최근 조정폭</span>
          <span class="em-value" style="color:${pbCol}">${pb5d.toFixed(1)}%</span>
        </div>
        <div class="em-bar-track">
          <div class="sweet" style="left:15%;width:45%;background:rgba(46,160,67,0.15)"></div>
          <div class="em-bar-fill" style="width:${pb5Bar}%;background:${pbCol}"></div>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 3~12% (건강한 조정)</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">RSI 상태</span>
          <span class="em-value" style="color:${rsiCol}">${rsiReset.toFixed(1)}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 42~60 (극단 과열/과매도 회피)</div>
      </div>
      <div class="em-item">
        <div class="em-header">
          <span class="em-label">ADX</span>
          <span class="em-value" style="color:${adx >= 20 ? '#2ea043' : 'var(--text2)'}">${adx.toFixed(1)}</span>
        </div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 20 이상 (추세 지속력)</div>
      </div>`;
  }
  const emaCol    = emaGood ? "#2ea043" : Math.abs(ema20GapPct) > 12 ? "#e53935" : "#d29922";
  const emaSign   = ema20GapPct >= 0 ? "+" : "";

  // BB 위치: sweet 35~75%
  const bbGood = bbPos >= 35 && bbPos <= 75;
  const bbCol  = bbGood ? "#2ea043" : bbPos > 85 ? "#e53935" : "#d29922";

  // 장기 위치: sweet 55~88%
  const p52Good = pos52 >= 55 && pos52 <= 88;
  const p52Col  = p52Good ? "#2ea043" : pos52 > 95 ? "#e53935" : "#d29922";

  // 최근 조정폭: sweet 4~12%
  const pbGood = pb5d >= 4 && pb5d <= 12;
  const pbCol  = pbGood ? "#2ea043" : pb5d > 15 ? "#e53935" : "#d29922";
  const pb5Bar = Math.min(100, pb5d / 20 * 100);

  const atrGapCol = ema20GapAtr >= -0.5 && ema20GapAtr <= 1.2 ? "#2ea043" : Math.abs(ema20GapAtr) > 3 ? "#e53935" : "#d29922";
  const rsiCol = rsiReset >= 45 && rsiReset <= 60 ? "#2ea043" : rsiReset > 72 || rsiReset < 30 ? "#e53935" : "#d29922";

  const compColor = (value, goodCut) => value >= goodCut ? "#2ea043" : value < 0 ? "#e53935" : "#d29922";

  document.getElementById("entryMetrics").innerHTML = `
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">추세 문맥</span>
        <span class="em-value" style="color:${compColor(trendCtx, 16)}">${trendCtx.toFixed(1)}</span>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">상승 우위 추세가 유지되는지 평가</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">눌림 품질</span>
        <span class="em-value" style="color:${compColor(pullback, 18)}">${pullback.toFixed(1)}</span>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">과열 해소와 RSI 리셋 상태</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">확인 신호</span>
        <span class="em-value" style="color:${compColor(confirm, 14)}">${confirm.toFixed(1)}</span>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">재상승 재개 여부와 종가 위치</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">저항 여유</span>
        <span class="em-value" style="color:${compColor(space, 10)}">${space.toFixed(1)}</span>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">상단 저항과 과열 부담 정도</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">EMA20 이격률</span>
        <span class="em-value" style="color:${emaCol}">${emaSign}${ema20GapPct.toFixed(1)}%</span>
      </div>
      <div class="em-bar-track">
        <div class="sweet" style="left:${(15/30)*100}%;width:${(8/30)*100}%;background:rgba(46,160,67,0.15)"></div>
        <div class="em-bar-fill" style="width:${emaBarPct}%;background:${emaCol}"></div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: -1~+4% (EMA 근접 눌림)</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">EMA20 ATR 이격</span>
        <span class="em-value" style="color:${atrGapCol}">${ema20GapAtr >= 0 ? "+" : ""}${ema20GapAtr.toFixed(2)} ATR</span>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: -0.5 ~ +1.2 ATR</div>
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
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 35~75% (과열 아닌 재상승권)</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">${rangeLabel || "장기 위치"}</span>
        <span class="em-value" style="color:${p52Col}">${pos52.toFixed(0)}%</span>
      </div>
      <div class="em-bar-track">
        <div class="sweet" style="left:55%;width:33%;background:rgba(46,160,67,0.15)"></div>
        <div class="em-bar-fill" style="width:${pos52}%;background:${p52Col}"></div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 55~88% (추세권, 상단 여유)</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">최근 조정폭</span>
        <span class="em-value" style="color:${pbCol}">${pb5d.toFixed(1)}%</span>
      </div>
      <div class="em-bar-track">
        <div class="sweet" style="left:20%;width:40%;background:rgba(46,160,67,0.15)"></div>
        <div class="em-bar-fill" style="width:${pb5Bar}%;background:${pbCol}"></div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 4~12% (건강한 눌림)</div>
    </div>
    <div class="em-item">
      <div class="em-header">
        <span class="em-label">RSI 리셋</span>
        <span class="em-value" style="color:${rsiCol}">${rsiReset.toFixed(1)}</span>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:2px">이상적: 45~60 (과열 해소 후 재가속 준비)</div>
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
