/* static/js/analyze.js */

const COL_LABELS = {
  Date: "날짜", Open: "시가", High: "고가", Low: "저가", Close: "종가",
  Volume: "거래량", EMA20: "EMA20", EMA60: "EMA60", RSI14: "RSI(14)",
  MACD: "MACD", FIS: "FIS", ICH_TENKAN: "전환선", ICH_KIJUN: "기준선",
  ICH_SENKOU_A: "선행A", ICH_SENKOU_B: "선행B",
};

let _chartMeta = null;
let _chartOverlayBound = false;
let _chartPinned = null;
const _chartView = {
  scale: 1,
  tx: 0,
  ty: 0,
  dragging: false,
  dragX: 0,
  dragY: 0,
  touchMode: null,
  pinchDist: 0,
};

function _chartEls() {
  return {
    stage: document.getElementById("chartStage"),
    viewport: document.getElementById("chartViewport"),
    transform: document.getElementById("chartTransform"),
    overlay: document.getElementById("chartOverlay"),
    eventLayer: document.getElementById("chartEventLayer"),
    crossX: document.getElementById("chartCrosshairX"),
    crossY: document.getElementById("chartCrosshairY"),
    xLabel: document.getElementById("chartXAxisLabel"),
    yLabel: document.getElementById("chartYAxisLabel"),
    tooltip: document.getElementById("chartHoverTooltip"),
  };
}

function _clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function _pct(value) {
  return `${(value * 100).toFixed(4)}%`;
}

function _viewportSize() {
  const { viewport } = _chartEls();
  if (!viewport) return { width: 1, height: 1 };
  return {
    width: Math.max(1, viewport.clientWidth || 1),
    height: Math.max(1, viewport.clientHeight || 1),
  };
}

function _clampPan(tx, ty, scale) {
  const size = _viewportSize();
  const maxX = Math.max(0, (scale - 1) * size.width);
  const maxY = Math.max(0, (scale - 1) * size.height);
  return {
    tx: _clamp(tx, -maxX, 0),
    ty: _clamp(ty, -maxY, 0),
  };
}

function _applyChartTransform() {
  const { transform } = _chartEls();
  if (!transform) return;
  const p = _clampPan(_chartView.tx, _chartView.ty, _chartView.scale);
  _chartView.tx = p.tx;
  _chartView.ty = p.ty;
  transform.style.transform = `translate(${_chartView.tx}px, ${_chartView.ty}px) scale(${_chartView.scale})`;
}

function _resetChartTransform() {
  _chartView.scale = 1;
  _chartView.tx = 0;
  _chartView.ty = 0;
  _chartView.dragging = false;
  _chartView.touchMode = null;
  _applyChartTransform();
}

function _zoomAt(clientX, clientY, factor) {
  const { viewport } = _chartEls();
  if (!viewport) return;
  const rect = viewport.getBoundingClientRect();
  const localX = clientX - rect.left;
  const localY = clientY - rect.top;
  const prevScale = _chartView.scale;
  const nextScale = _clamp(prevScale * factor, 1, 4.5);
  if (Math.abs(nextScale - prevScale) < 0.0001) return;

  const worldX = (localX - _chartView.tx) / prevScale;
  const worldY = (localY - _chartView.ty) / prevScale;

  _chartView.scale = nextScale;
  _chartView.tx = localX - worldX * nextScale;
  _chartView.ty = localY - worldY * nextScale;
  _applyChartTransform();
}

function _touchDistance(t0, t1) {
  const dx = t0.clientX - t1.clientX;
  const dy = t0.clientY - t1.clientY;
  return Math.hypot(dx, dy);
}

function _touchMidpoint(t0, t1) {
  return {
    x: (t0.clientX + t1.clientX) / 2,
    y: (t0.clientY + t1.clientY) / 2,
  };
}

function _chartValueText(panelKey, value) {
  if (panelKey === "volume") return fmtVol(Math.max(0, value));
  if (panelKey === "price") return fmt(value, 2);
  return Number(value || 0).toFixed(2);
}

function _hideChartTooltip() {
  const { tooltip } = _chartEls();
  if (!tooltip) return;
  tooltip.classList.add("hidden");
}

function _showChartTooltip(html, clientX, clientY) {
  const { overlay, tooltip } = _chartEls();
  if (!overlay || !tooltip) return;
  const rect = overlay.getBoundingClientRect();
  const localX = clientX - rect.left;
  const localY = clientY - rect.top;
  tooltip.innerHTML = html;
  tooltip.classList.remove("hidden");

  const pad = 14;
  const tipW = tooltip.offsetWidth;
  const tipH = tooltip.offsetHeight;
  let left = localX + pad;
  let top = localY + pad;
  if (left + tipW > rect.width - 8) left = localX - tipW - pad;
  if (top + tipH > rect.height - 8) top = localY - tipH - pad;
  tooltip.style.left = `${_clamp(left, 8, Math.max(8, rect.width - tipW - 8))}px`;
  tooltip.style.top = `${_clamp(top, 8, Math.max(8, rect.height - tipH - 8))}px`;
}

function _hideChartCrosshair() {
  const { crossX, crossY, xLabel, yLabel } = _chartEls();
  [crossX, crossY, xLabel, yLabel].forEach(el => el?.classList.add("hidden"));
}

function _updateCrosshairAtClient(clientX, clientY) {
  if (!_chartMeta) return;
  const { overlay, crossX, crossY, xLabel, yLabel } = _chartEls();
  if (!overlay) return;

  const rect = overlay.getBoundingClientRect();
  const x = (clientX - rect.left) / rect.width;
  const y = (clientY - rect.top) / rect.height;
  const plot = _chartMeta.plot_area;
  if (x < plot.left || x > plot.right || y < plot.top || y > plot.bottom) {
    _hideChartCrosshair();
    return;
  }

  let active = null;
  for (const [panelKey, panel] of Object.entries(_chartMeta.panels || {})) {
    if (x >= panel.left && x <= panel.right && y >= panel.top && y <= panel.bottom) {
      active = { key: panelKey, ...panel };
      break;
    }
  }
  if (!active) {
    _hideChartCrosshair();
    return;
  }

  const dataX = active.x_min + (((x - active.left) / Math.max(0.0001, active.width)) * (active.x_max - active.x_min));
  const idx = _clamp(Math.round(dataX), 0, Math.max(0, (_chartMeta.count || 1) - 1));
  const date = _chartMeta.dates?.[idx] || "";
  const relY = 1 - ((y - active.top) / Math.max(0.0001, active.height));
  const value = active.y_min + relY * (active.y_max - active.y_min);

  crossX.style.left = _pct(x);
  crossX.style.top = _pct(plot.top);
  crossX.style.height = _pct(plot.bottom - plot.top);
  crossX.classList.remove("hidden");

  crossY.style.left = _pct(active.left);
  crossY.style.top = _pct(y);
  crossY.style.width = _pct(active.right - active.left);
  crossY.classList.remove("hidden");

  xLabel.textContent = date;
  xLabel.style.left = _pct(x);
  xLabel.style.top = _pct(plot.bottom);
  xLabel.classList.remove("hidden");

  yLabel.textContent = _chartValueText(active.key, value);
  yLabel.style.left = _pct(active.right);
  yLabel.style.top = _pct(y);
  yLabel.classList.remove("hidden");
}

function _clearPinnedEvent() {
  _chartPinned = null;
  document.querySelectorAll(".chart-event-badge.active").forEach(el => el.classList.remove("active"));
}

function _drawChartCrosshair(panelKey, idx, value, date) {
  if (!_chartMeta) return;
  const { crossX, crossY, xLabel, yLabel } = _chartEls();
  const plot = _chartMeta.plot_area;
  const panel = _chartMeta.panels?.[panelKey];
  const pricePanel = _chartMeta.panels?.price;
  if (!panel || !pricePanel) return;

  const x = pricePanel.left + (((idx - pricePanel.x_min) / Math.max(0.0001, pricePanel.x_max - pricePanel.x_min)) * pricePanel.width);
  const y = panel.top + ((1 - ((value - panel.y_min) / Math.max(0.0001, panel.y_max - panel.y_min))) * panel.height);

  crossX.style.left = _pct(x);
  crossX.style.top = _pct(plot.top);
  crossX.style.height = _pct(plot.bottom - plot.top);
  crossX.classList.remove("hidden");

  crossY.style.left = _pct(panel.left);
  crossY.style.top = _pct(y);
  crossY.style.width = _pct(panel.right - panel.left);
  crossY.classList.remove("hidden");

  xLabel.textContent = date || "";
  xLabel.style.left = _pct(x);
  xLabel.style.top = _pct(plot.bottom);
  xLabel.classList.remove("hidden");

  yLabel.textContent = _chartValueText(panelKey, value);
  yLabel.style.left = _pct(panel.right);
  yLabel.style.top = _pct(y);
  yLabel.classList.remove("hidden");
}

function _bindChartOverlay() {
  if (_chartOverlayBound) return;
  const { overlay } = _chartEls();
  if (!overlay) return;

  overlay.addEventListener("mousemove", e => {
    if (_chartView.dragging || _chartPinned || _chartView.touchMode === "pan" || _chartView.touchMode === "pinch") return;
    _updateCrosshairAtClient(e.clientX, e.clientY);
  });

  overlay.addEventListener("wheel", e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    _zoomAt(e.clientX, e.clientY, factor);
  }, { passive: false });

  overlay.addEventListener("mousedown", e => {
    if (e.button !== 0) return;
    if (_chartView.scale <= 1.0001) return;
    if (e.target.closest(".chart-event-badge")) return;
    _chartView.dragging = true;
    _chartView.dragX = e.clientX;
    _chartView.dragY = e.clientY;
    overlay.classList.add("is-pan");
    e.preventDefault();
  });

  window.addEventListener("mousemove", e => {
    if (!_chartView.dragging) return;
    const dx = e.clientX - _chartView.dragX;
    const dy = e.clientY - _chartView.dragY;
    _chartView.dragX = e.clientX;
    _chartView.dragY = e.clientY;
    _chartView.tx += dx;
    _chartView.ty += dy;
    _applyChartTransform();
  });

  window.addEventListener("mouseup", () => {
    if (!_chartView.dragging) return;
    _chartView.dragging = false;
    overlay.classList.remove("is-pan");
  });

  overlay.addEventListener("touchstart", e => {
    if (!_chartMeta) return;
    if (e.touches.length === 2) {
      _chartView.touchMode = "pinch";
      _chartView.pinchDist = _touchDistance(e.touches[0], e.touches[1]);
      e.preventDefault();
      return;
    }
    if (e.touches.length === 1) {
      const t = e.touches[0];
      _chartView.dragX = t.clientX;
      _chartView.dragY = t.clientY;
      _chartView.touchMode = _chartView.scale > 1.0001 ? "pan" : "crosshair";
      if (_chartView.touchMode === "crosshair") {
        _updateCrosshairAtClient(t.clientX, t.clientY);
      }
      e.preventDefault();
    }
  }, { passive: false });

  overlay.addEventListener("touchmove", e => {
    if (!_chartMeta) return;
    if (e.touches.length === 2) {
      const dist = _touchDistance(e.touches[0], e.touches[1]);
      const mid = _touchMidpoint(e.touches[0], e.touches[1]);
      if (_chartView.pinchDist > 0) {
        const factor = dist / _chartView.pinchDist;
        _zoomAt(mid.x, mid.y, factor);
      }
      _chartView.pinchDist = dist;
      _chartView.touchMode = "pinch";
      e.preventDefault();
      return;
    }

    if (e.touches.length === 1) {
      const t = e.touches[0];
      if (_chartView.touchMode === "pan" && _chartView.scale > 1.0001) {
        const dx = t.clientX - _chartView.dragX;
        const dy = t.clientY - _chartView.dragY;
        _chartView.dragX = t.clientX;
        _chartView.dragY = t.clientY;
        _chartView.tx += dx;
        _chartView.ty += dy;
        _applyChartTransform();
      } else {
        _chartView.touchMode = "crosshair";
        _updateCrosshairAtClient(t.clientX, t.clientY);
      }
      e.preventDefault();
    }
  }, { passive: false });

  overlay.addEventListener("touchend", e => {
    if (e.touches.length === 0) {
      _chartView.touchMode = null;
      _chartView.pinchDist = 0;
      if (!_chartPinned) {
        _hideChartTooltip();
      }
    } else if (e.touches.length === 1 && _chartView.scale > 1.0001) {
      _chartView.touchMode = "pan";
      _chartView.dragX = e.touches[0].clientX;
      _chartView.dragY = e.touches[0].clientY;
    }
  });

  overlay.addEventListener("mouseleave", () => {
    if (_chartPinned) return;
    _hideChartCrosshair();
    _hideChartTooltip();
  });

  overlay.addEventListener("click", e => {
    if (e.target.closest(".chart-event-badge")) return;
    _clearPinnedEvent();
    _hideChartCrosshair();
    _hideChartTooltip();
  });

  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    _clearPinnedEvent();
    _hideChartCrosshair();
    _hideChartTooltip();
  });

  _chartOverlayBound = true;
}

function _renderChartOverlay(meta) {
  _chartMeta = meta || null;
  _clearPinnedEvent();
  const { eventLayer } = _chartEls();
  if (!eventLayer) return;
  eventLayer.innerHTML = "";
  _hideChartCrosshair();
  _hideChartTooltip();
  _resetChartTransform();
  _bindChartOverlay();
  if (!_chartMeta) return;

  (_chartMeta.events || []).forEach(ev => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chart-event-badge";
    btn.textContent = ev.label;
    btn.style.left = _pct(ev.x);
    btn.style.top = _pct(ev.y);
    btn.style.setProperty("--badge-color", ev.color || "#303030");

    const tooltipHtml = `
      <div class="chart-tooltip-title">${ev.label}</div>
      <div class="chart-tooltip-meta">날짜: ${ev.date}</div>
      <div class="chart-tooltip-meta">값: ${_chartValueText(ev.panel, ev.value)}</div>
      <div class="chart-tooltip-desc">${ev.description || ""}</div>`;

    btn.addEventListener("mouseenter", e => _showChartTooltip(tooltipHtml, e.clientX, e.clientY));
    btn.addEventListener("mousemove", e => _showChartTooltip(tooltipHtml, e.clientX, e.clientY));
    btn.addEventListener("mouseleave", () => _hideChartTooltip());
    btn.addEventListener("click", e => {
      e.preventDefault();
      e.stopPropagation();
      const isSame = _chartPinned && _chartPinned.type === ev.type && _chartPinned.idx === ev.idx;
      if (isSame) {
        _clearPinnedEvent();
        _hideChartCrosshair();
        return;
      }
      _clearPinnedEvent();
      btn.classList.add("active");
      _chartPinned = { type: ev.type, idx: ev.idx };
      _drawChartCrosshair(ev.panel, ev.idx, ev.value, ev.date);
    });
    eventLayer.appendChild(btn);
  });
}

function renderEntryScore(entry, l, rangeLabel) {
    const score      = entry?.score ?? 0;
    const components = entry?.components || {};
    const setupName  = entry?.setup_name  || "일반";
    const setupName2 = entry?.setup_name2 || "";
    const setupScores = entry?.setup_scores || {};
    const metrics    = entry?.metrics || {};

    const ctx      = components["추세문맥"]   ?? 0;
    const structure = components["진입구조"]  ?? 0;
    const confirm  = components["확인신호"]   ?? 0;
    const space    = components["저항여유"]   ?? 0;
    const riskCtrl = components["리스크관리"] ?? 0;

    // ── 진입점수 배지 ──────────────────────────────────────
    const eCol = score >= 80 ? "#2ea043" : score >= 65 ? "#56d364" : score >= 50 ? "#d29922" : "#6e7681";
    const badge = document.getElementById("entryScoreBadge");
    badge.textContent      = `${score.toFixed(0)}`;
    badge.style.background = eCol;

    let statusText;
    if      (score >= 80) statusText = `최적 진입 구간`;
    else if (score >= 65) statusText = `양호한 진입 구간`;
    else if (score >= 50) statusText = `조건부 진입 가능`;
    else                  statusText = `진입 대기 구간`;
    document.getElementById("entryStatus").textContent = statusText;

    // ── 보조 수치 ──────────────────────────────────────────
    const ema20GapPct = l.ema20_gap_pct ?? 0;
    const ema20GapAtr = l.ema20_gap_atr ?? 0;
    const bbPos       = l.bb_pos        ?? 50;
    const pos52       = l.pos52         ?? 50;
    const pb5d        = l.pullback_5d   ?? 0;
    const rsiVal      = metrics.rsi_reset ?? l.rsi ?? 50;
    const adx         = metrics.adx ?? 0;

    function compColor(v, good, danger) {
      return v >= good ? "#2ea043" : v < (danger ?? -9999) ? "#e53935" : "#d29922";
    }
    function valColor(v, lo, hi, revLo, revHi) {
      if (v >= lo && v <= hi) return "#2ea043";
      if (v < (revLo ?? -Infinity) || v > (revHi ?? Infinity)) return "#e53935";
      return "#d29922";
    }
    function bar(pct, col) {
      return `<div class="em-bar-track"><div class="em-bar-fill" style="width:${Math.min(100,Math.max(0,pct))}%;background:${col}"></div></div>`;
    }
    function sweet(lo, hi, col="rgba(46,160,67,0.15)") {
      return `<div class="sweet" style="left:${lo}%;width:${hi-lo}%;background:${col}"></div>`;
    }
    function fullBar(pct, lo, hi, col) {
      return `<div class="em-bar-track">${sweet(lo,hi)}${bar(pct,col).replace('<div class="em-bar-track">','').replace('</div>','')}</div>`;
    }

    // ── 시나리오 설명 ──────────────────────────────────────
    const setupDesc = {
      "추세 눌림":   "상승 추세 중 EMA 근처로 눌렸다가 재반등하는 구조. RSI 과열 해소 + 거래량 감소 후 반등이 핵심.",
      "압축 돌파":   "좁은 횡보로 에너지 압축 후 거래량 동반 상단 돌파. ATR·BB 수축 후 확장 시도.",
      "모멘텀 지속": "정배열(EMA10>20>60) 강세 추세에서 지속 상승. ROC·거래량 강세 유지가 핵심.",
      "반전 초기":   "과매도 후 바닥 반전 초기 신호. MACD 반전 + RSI 저점 반등 + 거래량 증가 확인."
    };
    const setupChips = Object.entries(setupScores)
      .sort((a,b) => b[1]-a[1])
      .map(([k,v]) => {
        const isBest = k === setupName;
        const is2nd  = k === setupName2;
        return `<span class="em-chip${isBest?" em-chip-best":is2nd?" em-chip-2nd":""}">${k} <b>${v.toFixed(0)}</b></span>`;
      }).join("");

    // ── 5개 구성요소 카드 ──────────────────────────────────
    const compRows = [
      {
        num: "①", name: "추세 문맥", v: ctx, max: 30,
        ideal: "24 이상이 최적",
        desc: ctx >= 24 ? "FIS·추세·ADX·구름 모두 매수 환경 충족"
             : ctx >= 16 ? "추세 방향 우세 — 일부 조건 미충족"
             : ctx >= 8  ? "중립 이상 — 추세 약세에 주의"
             : "추세 환경 부족 — 신중 접근",
      },
      {
        num: "②", name: `진입 구조 — ${setupName}${setupName2 ? " + "+setupName2 : ""}`,
        v: structure, max: 30,
        ideal: "20 이상이 최적",
        desc: setupDesc[setupName] || "—",
        extra: `<div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:5px">${setupChips}</div>`,
      },
      {
        num: "③", name: "확인 신호", v: confirm, max: 24,
        ideal: "16 이상이 최적",
        desc: confirm >= 18 ? "EMA·MACD·거래량·기준선 신호 모두 동반"
             : confirm >= 12 ? "핵심 신호 대부분 확인"
             : confirm >= 6  ? "일부 신호만 충족 — 추가 봉 확인 권장"
             : "명확한 진입 신호 아직 부족",
      },
      {
        num: "④", name: "저항 여유", v: space, max: 18,
        ideal: "10 이상이 최적",
        desc: space >= 12 ? "52주·BB 상단 여유 충분 — 저항 부담 낮음"
             : space >= 6  ? "적정 상승 공간 확인"
             : space >= 0  ? "일부 저항 부담 있음"
             : "상단 저항 과부담 — 추격 매수 불리",
      },
      {
        num: "⑤", name: "리스크 관리", v: riskCtrl, max: 16,
        ideal: "10 이상이 최적",
        desc: riskCtrl >= 12 ? "과열 없고 손절 거리 적정 — 위험 관리 양호"
             : riskCtrl >= 8  ? "리스크 통제 가능 수준"
             : riskCtrl >= 4  ? "일부 위험 요소 — 손절 기준 명확히 설정"
             : "ATR 이격 크거나 위험감점 높음 — 주의",
      },
    ].map(r => {
      const pct = r.max > 0 ? r.v / r.max * 100 : 0;
      const col = compColor(r.v, r.max * 0.7, r.max * 0.3);
      return `<div class="es-comp">
        <div class="es-comp-hd">
          <span class="es-comp-num">${r.num}</span>
          <span class="es-comp-name">${r.name}</span>
          <span class="es-comp-score" style="color:${col}">${r.v.toFixed(0)} <span class="es-comp-max">/ ${r.max}</span></span>
        </div>
        <div class="es-comp-bar"><div style="width:${Math.min(100,Math.max(0,pct))}%;background:${col}"></div></div>
        <div class="es-comp-desc">${r.desc}</div>
        ${r.extra || ""}
      </div>`;
    }).join("");

    // ── 시장 수치 요약 ──────────────────────────────────────
    const emaSign   = ema20GapPct >= 0 ? "+" : "";
    const emaCol    = valColor(ema20GapPct, -1, 4,  null, 12);
    const atrCol    = valColor(ema20GapAtr, -0.5, 1.2, null, 3);
    const bbCol     = valColor(bbPos, 35, 75, null, 90);
    const p52Col    = valColor(pos52, 55, 90, null, 97);
    const pbCol     = valColor(pb5d, 3, 12, null, 20);
    const rsiCol    = valColor(rsiVal, 42, 60, 30, 73);
    const adxCol    = adx >= 20 ? "#2ea043" : adx >= 15 ? "#d29922" : "#e53935";
    const adxTip    = adx < 15 ? " ⚠ 방향성 약" : "";

    const metricRows = [
      { label:"EMA20 이격",   value:`${emaSign}${ema20GapPct.toFixed(1)}%`,   col:emaCol,  ideal:"-1~+4% 이상적",  warn: Math.abs(ema20GapPct)>8  },
      { label:"ATR 이격",     value:`${ema20GapAtr>=0?"+":""}${ema20GapAtr.toFixed(2)} ATR`, col:atrCol, ideal:"-0.5~+1.2 이상적", warn: Math.abs(ema20GapAtr)>2.5 },
      { label:"RSI",          value:rsiVal.toFixed(1),             col:rsiCol,  ideal:"42~60 이상적",     warn: rsiVal>72||rsiVal<30 },
      { label:"BB 위치",      value:`${bbPos.toFixed(0)}%`,        col:bbCol,   ideal:"35~75% 이상적",    warn: bbPos>88 },
      { label:"52주 위치",    value:`${pos52.toFixed(0)}%`,        col:p52Col,  ideal:"55~90% 이상적",    warn: pos52>95 },
      { label:"최근 조정폭",  value:`${pb5d.toFixed(1)}%`,         col:pbCol,   ideal:"3~12% 이상적",     warn: pb5d>20||pb5d<1 },
      { label:"ADX",          value:`${adx.toFixed(1)}${adxTip}`, col:adxCol,  ideal:"20+ 추세 지속력",  warn: adx<15 },
    ].map(m => `
      <div class="es-metric-row">
        <span class="es-metric-label">${m.label}</span>
        <span class="es-metric-value" style="color:${m.col}">${m.value}${m.warn ? " !" : ""}</span>
        <span class="es-metric-ideal">${m.ideal}</span>
      </div>`).join("");

    document.getElementById("entryMetrics").innerHTML = compRows +
      `<div class="es-metric-block"><div class="es-metric-title">📐 세부 수치</div>${metricRows}</div>`;
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

// ── 전역 상태 ────────────────────────────────────────────
let _currentTicker = null;
let _currentName   = "";
let _currentPrice  = 0;
let _currentATR    = 0;
let _currentSetup  = "";
let _currentHigh20 = 0;
let _currentEMA20  = 0;
let _heldQty       = 0;
let _sellFullMode  = false;

// ── 유틸 ─────────────────────────────────────────────────
function fmtP(v) {
  const n = typeof v === "number" ? v : parseFloat(v);
  if (isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {maximumFractionDigits: 0});
}

function pctFromEntry(target, entry) {
  if (!entry) return "";
  const p = (target - entry) / entry * 100;
  return (p >= 0 ? "+" : "") + p.toFixed(1) + "%";
}

function onModalQtyChange() {
  const qty   = parseInt(document.getElementById("modalQty").value)   || 1;
  const price = parseFloat(document.getElementById("modalPrice").value) || _currentPrice;
  document.getElementById("modalInvest").textContent = fmtP(price * qty) + "원";
}

function onModalPriceChange() {
  const qty   = parseInt(document.getElementById("modalQty").value)   || 1;
  const price = parseFloat(document.getElementById("modalPrice").value) || 0;
  document.getElementById("modalInvest").textContent = price ? fmtP(price * qty) + "원" : "—";
}

// ── 매수/매도 모달 ─────────────────────────────────────────
function openBuyModal() {
  const entry = Math.round(_currentPrice);
  const ts    = _currentHigh20 > 0 ? Math.round(_currentHigh20 - _currentATR * 2) : 0;

  document.getElementById("modalTitle").textContent        = "신규 진입 등록";
  document.getElementById("modalSubTicker").textContent    = `${_currentName} (${_currentTicker})`;
  document.getElementById("modalScenarioChip").textContent = _currentSetup || "분석";
  document.getElementById("modalPrice").value              = entry;
  document.getElementById("modalQty").value                = 1;
  document.getElementById("modalInvest").textContent       = fmtP(entry) + "원";

  document.getElementById("modalTrailingStop").textContent = ts > 0 ? fmtP(ts) : "—";
  document.getElementById("modalTrailingPct").textContent  = ts > 0 ? pctFromEntry(ts, entry) : "";
  document.getElementById("modalEMA20").textContent        = _currentEMA20 > 0 ? fmtP(_currentEMA20) : "—";
  document.getElementById("modalEMASignal").textContent    = _currentEMA20 > 0
    ? (entry >= _currentEMA20 ? "✓ 상회" : "⬇ 하회 중") : "";

  document.getElementById("modalBuySection").style.display  = "";
  document.getElementById("modalSellSection").style.display = "none";
  document.getElementById("tradeModal").style.display = "flex";
  document.getElementById("modalQty").focus();
}

function openSellModal(isFull) {
  _sellFullMode = !!isFull;
  if (_heldQty <= 0) {
    showToast("보유 수량이 없어 매도할 수 없습니다.", "error");
    return;
  }

  document.getElementById("modalSellSub").textContent       = `${_currentName} (${_currentTicker})`;
  document.getElementById("modalSellSection").style.display = "";
  document.getElementById("modalBuySection").style.display  = "none";
  document.getElementById("tradeModal").style.display = "flex";
  const qtyInput = document.getElementById("modalSellQty");
  qtyInput.max = _heldQty;
  qtyInput.value = isFull ? _heldQty : 1;
  qtyInput.disabled = !!isFull;

  const note = document.getElementById("modalSellModeNote");
  if (note) {
    note.textContent = isFull
      ? `전량 매도 모드 · 보유 ${_heldQty.toLocaleString("ko-KR")}주 전부 매도`
      : `부분 매도 모드 · 보유 ${_heldQty.toLocaleString("ko-KR")}주 중 일부 매도`;
  }
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
    body: JSON.stringify({
      ticker: _currentTicker, name: _currentName, qty, price,
    })
  }).then(r => r.json());
  closeTradeModal();
  if (res.ok) showToast(`${_currentName} ${qty}주 진입 등록 완료`);
  else        showToast("오류: " + res.error, "error");
}

async function confirmSell() {
  const qty = parseInt(document.getElementById("modalSellQty").value);
  if (_sellFullMode) {
    submitSell(0);
    return;
  }
  if (!qty || qty < 1) { alert("매도 수량을 입력하세요."); return; }
  if (qty > _heldQty) { alert("보유 수량보다 많은 매도는 불가합니다."); return; }
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

// ── URL 파라미터 ─────────────────────────────────────────
function getTickerFromURL() {
  return new URLSearchParams(window.location.search).get("ticker");
}

// ── 토스트 알림 ───────────────────────────────────────────
function showToast(msg, type = "success") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.style.background = type === "error" ? "#c62828" : "#2ea043";
  el.style.display = "block";
  el.style.opacity = "1";
  setTimeout(() => {
    el.style.opacity = "0";
    setTimeout(() => { el.style.display = "none"; }, 400);
  }, 3000);
}

// ── 종목 차트 분석 ────────────────────────────────────────
async function loadAnalysis(ticker) {
  _currentTicker = ticker.toUpperCase();
  document.getElementById("loadingOverlay").style.display = "flex";
  document.getElementById("analyzeMain").style.display    = "none";

  const period    = document.getElementById("periodSelect")?.value    || "2y";
  const timeframe = document.getElementById("timeframeSelect")?.value || "daily";

  try {
    const res = await fetch(
      `/api/analyze/${encodeURIComponent(_currentTicker)}?period=${encodeURIComponent(period)}&timeframe=${encodeURIComponent(timeframe)}&bars=220`
    );
    const d = await res.json();
    if (!d.ok) { alert("분석 오류: " + (d.error || "")); hideLoading(); return; }

    const j = d.judgment;
    const l = d.latest;

    _currentName  = d.info?.name || _currentTicker;
    _currentPrice = l.close;
    _currentATR   = l.atr   || 0;
    _currentSetup = d.entry?.setup_name || "";
    _currentHigh20 = l.high20 || 0;
    _currentEMA20  = l.ema20  || 0;

    // 종목 헤더
    document.getElementById("stockName").textContent     = _currentName;
    document.getElementById("stockTicker").textContent   = _currentTicker;
    document.getElementById("stockExchange").textContent = d.info?.exchange || "";
    document.getElementById("stockMeta").textContent     =
      [d.info?.sector, d.info?.industry].filter(Boolean).join(" · ");

    const sign   = l.day_change_pct >= 0 ? "+" : "";
    const chgCol = l.day_change_pct >= 0 ? "var(--bull)" : "var(--bear)";
    document.getElementById("stockPrice").textContent    = fmt(l.close);
    document.getElementById("stockCurrency").textContent = d.info?.currency || "";
    document.getElementById("stockDayChg").textContent   =
      `${sign}${fmt(l.day_change_abs)} (${sign}${(l.day_change_pct ?? 0).toFixed(2)}%)`;
    document.getElementById("stockDayChg").style.color   = chgCol;

    // FIS 배지
    const fCol  = fisColor(l.fis);
    const fBadge = document.getElementById("fisBadge");
    fBadge.textContent      = `FIS ${l.fis >= 0 ? "+" : ""}${l.fis.toFixed(1)}`;
    fBadge.style.background = fCol;
    const lChip = document.getElementById("labelChip");
    lChip.textContent = j.label;
    lChip.style.color = fCol;

    // 판단 텍스트
    document.getElementById("judgeL1").textContent    = j.summary_l1;
    document.getElementById("judgeL2").textContent    = j.summary_l2 || "";
    document.getElementById("judgeExtra").textContent =
      `${d.timeframe_label || "일봉"} 기준 · ${d.range_label || "장기 위치"} ${(l.pos52 ?? 0).toFixed(0)}%`;

    // 점수 바 — j.scores 딕셔너리에서 읽음
    const sc = j.scores || {};
    const scoreItems = [
      { label: "추세",      value: sc["추세"]     ?? 0, max: 30 },
      { label: "모멘텀",    value: sc["모멘텀"]   ?? 0, max: 20 },
      { label: "구조",      value: sc["구조"]     ?? 0, max: 20 },
      { label: "압축/위치", value: sc["압축"]     ?? 0, max: 20 },
      { label: "거래량",    value: sc["거래량"]   ?? 0, max: 10 },
      { label: "위험감점",  value: sc["위험감점"] ?? 0, max: 0  },
    ];
    document.getElementById("scoreBars").innerHTML = scoreItems.map(b => {
      const isRisk = b.label === "위험감점";
      const pct = b.max > 0
        ? Math.min(100, Math.max(0, (b.value / b.max) * 100))
        : Math.min(100, Math.abs(b.value ?? 0) * 3);
      const col = isRisk
        ? ((b.value ?? 0) < -12 ? "var(--bear)" : "var(--text3)")
        : ((b.value ?? 0) >= 0 ? "var(--bull)" : "var(--bear)");
      const sign = (b.value ?? 0) >= 0 ? "+" : "";
      return `<div class="sb-row">
        <span class="sb-label">${b.label}</span>
        <div class="sb-track"><div class="sb-fill" style="width:${pct}%;background:${col}"></div></div>
        <span class="sb-val" style="color:${col}">${sign}${(b.value ?? 0).toFixed(1)}</span>
      </div>`;
    }).join("");

    // 진입 점수
    renderEntryScore(d.entry, l, d.range_label);

    // 차트
    document.getElementById("mainChart").src = "data:image/png;base64," + d.chart;
    _renderChartOverlay(d.chart_meta);

    // 보유 정보 배지
    const isHolding = !!(d.holding && d.holding.is_holding);
    _heldQty = isHolding ? Number(d.holding.quantity || 0) : 0;
    document.getElementById("holdingBadge").style.display = isHolding ? "inline-block" : "none";

    // 지표 칩
    renderChips(j, l);

    // 테이블
    buildTable(d.table);

    hideLoading();
    document.getElementById("analyzeMain").style.display = "block";
  } catch (e) {
    alert("분석 실패: " + e.message);
    hideLoading();
  }
}

function reloadChart() {
  if (_currentTicker) loadAnalysis(_currentTicker);
}

document.addEventListener("DOMContentLoaded", () => {
  const t = getTickerFromURL();
  if (t) loadAnalysis(t); else window.location.href = "/";
  document.getElementById("tradeModal")?.addEventListener("click", e => {
    if (e.target.id === "tradeModal") closeTradeModal();
  });
});
