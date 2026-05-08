"""api/server.py — Flask REST API 백엔드"""

import os
import traceback
from flask import Flask, request, jsonify, send_from_directory

from engine.data      import (
    fetch,
    calc_indicators,
    get_info,
    search_ticker,
    fetch_market_index,
    normalize_timeframe,
    resolve_fetch_period,
    resample_ohlcv,
)
from engine.fis       import calc_fis, make_judgment, calc_entry_score
from engine.chart     import render_main_chart, render_mini_chart
from engine.market    import get_market_summary
from engine.scanner   import scan_market
from engine.portfolio import buy as port_buy, sell as port_sell, get_positions

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TMPL_DIR   = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TMPL_DIR)


def _signal_snapshot(ticker: str, period: str = "1y", timeframe: str = "daily") -> dict:
    fetch_period = resolve_fetch_period(period, timeframe)
    raw_df = fetch(ticker, fetch_period)
    price_df = resample_ohlcv(raw_df, timeframe)
    ind_df = calc_indicators(price_df, timeframe)
    fis_df = calc_fis(ind_df)
    judgment = make_judgment(fis_df)
    entry = calc_entry_score(fis_df)
    row = fis_df.iloc[-1]
    return {
        "fis": float(row.get("FIS") or 0),
        "entry_score": float(entry["score"]),
        "risk": float(row.get("RiskPenalty") or 0),
        "trend": float(row.get("TrendScore") or 0),
        "label": judgment["label"],
        "summary_l1": judgment["summary_l1"],
        "setup_name": entry.get("setup_name", "일반"),
    }


def _portfolio_analysis(enriched: list) -> dict | None:
    analyzable = [p for p in enriched if p.get("fis") is not None]
    if not analyzable:
        return None

    total_value = sum(max(p["value"], 0) for p in analyzable) or 1.0
    weights = [p["value"] / total_value for p in analyzable]
    weighted_fis = sum(p["fis"] * w for p, w in zip(analyzable, weights))
    weighted_entry = sum(p["entry_score"] * w for p, w in zip(analyzable, weights))
    weighted_risk = sum(p["risk"] * w for p, w in zip(analyzable, weights))

    concentration = sum(w * w for w in weights)
    if len(weights) > 1:
        diversification = max(0.0, min(100.0, ((1 - concentration) / (1 - 1 / len(weights))) * 100))
    else:
        diversification = 0.0

    strongest = max(analyzable, key=lambda item: item["fis"] + item["entry_score"] * 0.5)
    weakest = min(analyzable, key=lambda item: item["fis"] + item["entry_score"] * 0.35 + item["risk"])

    if weighted_fis >= 45 and weighted_entry >= 65:
        label, label_color = "공격 유지 가능", "#D32F2F"
        summary_l1 = "보유 포트폴리오의 차트 우위가 전반적으로 살아 있고, 추가 매수 타이밍도 평균 이상이다."
        summary_l2 = "다만 집중도가 높다면 가장 강한 종목 위주로만 추가하고, 약한 종목 비중은 재점검하는 편이 낫다."
    elif weighted_fis >= 20:
        label, label_color = "선별 대응 구간", "#F9A825"
        summary_l1 = "포트폴리오 전체 방향은 아직 무너지지 않았지만, 종목별 강도 차이가 커서 선별 대응이 필요하다."
        summary_l2 = "강한 종목은 유지 가능하지만, 약한 종목은 비중 축소나 교체 검토가 필요하다."
    else:
        label, label_color = "방어 우선 구간", "#1565C0"
        summary_l1 = "포트폴리오 전체 우위가 약해졌다. 신규 추가 매수보다 방어와 정리가 우선이다."
        summary_l2 = "가장 약한 종목부터 정리 기준을 세우고, 진입 점수가 높은 종목만 제한적으로 보는 편이 낫다."

    return {
        "weighted_fis": round(weighted_fis, 1),
        "weighted_entry_score": round(weighted_entry, 1),
        "weighted_risk": round(weighted_risk, 1),
        "diversification_score": round(diversification, 1),
        "label": label,
        "label_color": label_color,
        "summary_l1": summary_l1,
        "summary_l2": summary_l2,
        "strongest_name": strongest["name"],
        "weakest_name": weakest["name"],
    }


# ── 페이지 라우트 ─────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(TMPL_DIR, "index.html")

@app.route("/analyze")
def analyze_page():
    return send_from_directory(TMPL_DIR, "analyze.html")

@app.route("/scan")
def scan_page():
    return send_from_directory(TMPL_DIR, "scan.html")

@app.route("/mypage")
def mypage():
    return send_from_directory(TMPL_DIR, "mypage.html")

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


# ── API: 시장 ─────────────────────────────────────────────

@app.route("/api/market")
def api_market():
    try:
        return jsonify({"ok": True, "data": get_market_summary()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API: 검색 ─────────────────────────────────────────────

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"ok": False, "error": "query required"}), 400
    try:
        return jsonify({"ok": True, "results": search_ticker(q)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API: 종목 분석 ────────────────────────────────────────

@app.route("/api/analyze/<ticker>")
def api_analyze(ticker: str):
    period = request.args.get("period", "2y")
    timeframe = normalize_timeframe(request.args.get("timeframe", "daily"))
    bars   = int(request.args.get("bars", 220))
    try:
        fetch_period = resolve_fetch_period(period, timeframe)
        raw_df    = fetch(ticker, fetch_period)
        price_df  = resample_ohlcv(raw_df, timeframe)
        ind_df    = calc_indicators(price_df, timeframe)
        fis_df    = calc_fis(ind_df)
        judgment  = make_judgment(fis_df)
        chart_b64 = render_main_chart(fis_df, judgment, ticker, bars, timeframe)

        recent = fis_df.iloc[-30:].copy()
        recent.index = recent.index.strftime("%Y-%m-%d")
        cols = ["Open","High","Low","Close","Volume",
                "EMA20","EMA60","RSI14","MACD","FIS",
                "ICH_TENKAN","ICH_KIJUN","ICH_SENKOU_A","ICH_SENKOU_B"]
        recent = recent[[c for c in cols if c in recent.columns]].round(2)
        table  = recent.reset_index().rename(columns={"index": "Date"}).to_dict("records")

        info = get_info(ticker)
        last = fis_df.iloc[-1]

        # ── 진입 타이밍 점수 ──────────────────────────────────
        entry = calc_entry_score(fis_df)

        # ── 추가 지표 계산 ────────────────────────────────────
        c = float(last["Close"])
        metrics = entry["metrics"]
        ema20_gap_pct = float(metrics.get("ema20_gap_pct", 0.0))
        ema20_gap_atr = float(metrics.get("ema20_gap_atr", 0.0))
        bb_pos = float(metrics.get("bb_pos", 50.0))
        pos52 = float(metrics.get("range_pos", 50.0))
        pullback_5d = float(metrics.get("pullback_pct", 0.0))

        timeframe_label_map = {
            "daily": "일봉",
            "weekly": "주봉",
            "monthly": "월봉",
            "yearly": "년봉",
        }
        range_label_map = {
            "daily": "52주 위치",
            "weekly": "2년 위치",
            "monthly": "5년 위치",
            "yearly": "장기 위치",
        }

        prev_close = float(fis_df.iloc[-2]["Close"]) if len(fis_df) >= 2 else c
        day_change_pct = round((c - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0.0
        day_change_abs = round(c - prev_close, 4)

        return jsonify({
            "ok": True, "ticker": ticker, "info": info,
            "judgment": judgment, "chart": chart_b64, "table": table,
            "entry_score": round(entry["score"], 1),
            "entry": entry,
            "timeframe": timeframe,
            "timeframe_label": timeframe_label_map.get(timeframe, "일봉"),
            "range_label": range_label_map.get(timeframe, "장기 위치"),
            "latest": {
                "close":         c,
                "fis":           float(last["FIS"]),
                "rsi":           float(last.get("RSI14") or 0),
                "rvol":          float(last.get("RVOL")  or 1),
                "atr":           float(last.get("ATR14") or 0),
                "ema20_gap_pct": ema20_gap_pct,
                "ema20_gap_atr": ema20_gap_atr,
                "bb_pos":        bb_pos,
                "pos52":         pos52,
                "pullback_5d":   pullback_5d,
                "day_change_pct": day_change_pct,
                "day_change_abs": day_change_abs,
            }
        })
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()}), 500


# ── API: 미니차트 ─────────────────────────────────────────

@app.route("/api/minichart/<ticker>")
def api_minichart(ticker: str):
    try:
        raw_df = fetch(ticker, "6mo")
        ind_df = calc_indicators(raw_df)
        fis_df = calc_fis(ind_df)
        fis    = float(fis_df.iloc[-1]["FIS"])
        b64    = render_mini_chart(ind_df, ticker, fis)
        return jsonify({"ok": True, "chart": b64, "fis": fis,
                        "close": float(fis_df.iloc[-1]["Close"])})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API: 신규 진입 종목 스캔 ──────────────────────────────

@app.route("/api/scan/<market>")
def api_scan(market: str):
    if market.lower() not in ("kospi", "kosdaq", "us"):
        return jsonify({"ok": False, "error": "market must be kospi|kosdaq|us"}), 400
    try:
        candidates = scan_market(market)
        return jsonify({"ok": True, "market": market, "candidates": candidates})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()}), 500


# ── API: 포트폴리오 조회 ──────────────────────────────────

@app.route("/api/portfolio")
def api_portfolio():
    try:
        positions = get_positions()
        enriched  = []
        for ticker, pos in positions.items():
            try:
                idx   = fetch_market_index(ticker)
                cur   = idx.get("price") or pos["avg_price"]
                chg   = idx.get("change_pct") or 0
            except Exception:
                cur, chg = pos["avg_price"], 0
            try:
                signal = _signal_snapshot(ticker)
            except Exception:
                signal = {
                    "fis": None,
                    "entry_score": None,
                    "risk": None,
                    "trend": None,
                    "label": "분석 실패",
                    "summary_l1": "현재 차트 분석 데이터를 불러오지 못했습니다.",
                    "setup_name": "정보 부족",
                }
            qty     = pos["quantity"]
            avg     = pos["avg_price"]
            value   = round(cur * qty, 2)
            cost    = round(avg * qty, 2)
            profit  = round(value - cost, 2)
            pct     = round((profit / cost * 100) if cost > 0 else 0, 2)
            enriched.append({
                "ticker":        ticker,
                "name":          pos["name"],
                "quantity":      qty,
                "avg_price":     avg,
                "current_price": cur,
                "day_change_pct":chg,
                "value":         value,
                "cost":          cost,
                "profit":        profit,
                "profit_pct":    pct,
                "fis":           signal["fis"],
                "entry_score":   signal["entry_score"],
                "risk":          signal["risk"],
                "trend":         signal["trend"],
                "signal_label":  signal["label"],
                "signal_summary": signal["summary_l1"],
                "setup_name":    signal["setup_name"],
            })
        total_cost   = round(sum(p["cost"]   for p in enriched), 2)
        total_value  = round(sum(p["value"]  for p in enriched), 2)
        total_profit = round(total_value - total_cost, 2)
        total_pct    = round((total_profit / total_cost * 100) if total_cost > 0 else 0, 2)
        return jsonify({
            "ok": True,
            "positions":    enriched,
            "summary": {
                "total_cost":   total_cost,
                "total_value":  total_value,
                "total_profit": total_profit,
                "total_pct":    total_pct,
            },
            "analysis": _portfolio_analysis(enriched),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API: 매수 ─────────────────────────────────────────────

@app.route("/api/portfolio/buy", methods=["POST"])
def api_buy():
    body = request.get_json(silent=True) or {}
    ticker     = body.get("ticker", "").strip().upper()
    name       = body.get("name", ticker)
    qty        = int(body.get("qty", 0))
    price      = float(body.get("price", 0))
    stop_price = body.get("stop_price")
    target1    = body.get("target1")
    target2    = body.get("target2")
    setup_name = body.get("setup_name", "")
    entry_atr  = body.get("entry_atr")
    if not ticker:
        return jsonify({"ok": False, "error": "ticker 필요"}), 400
    try:
        result = port_buy(
            ticker, name, qty, price,
            stop_price=float(stop_price) if stop_price else None,
            target1=float(target1)       if target1    else None,
            target2=float(target2)       if target2    else None,
            setup_name=setup_name,
            entry_atr=float(entry_atr)   if entry_atr  else None,
        )
        return jsonify({"ok": True, "position": result})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API: 매도 ─────────────────────────────────────────────

@app.route("/api/portfolio/sell", methods=["POST"])
def api_sell():
    body   = request.get_json(silent=True) or {}
    ticker = body.get("ticker", "").strip().upper()
    qty    = int(body.get("qty", 0))
    if not ticker:
        return jsonify({"ok": False, "error": "ticker 필요"}), 400
    try:
        result = port_sell(ticker, qty)
        return jsonify({"ok": True, **result})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def create_app():
    return app
