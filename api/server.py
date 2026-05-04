"""api/server.py — Flask REST API 백엔드"""

import os
import traceback
from flask import Flask, request, jsonify, send_from_directory

from engine.data      import fetch, calc_indicators, get_info, search_ticker, fetch_market_index
from engine.fis       import calc_fis, make_judgment
from engine.chart     import render_main_chart, render_mini_chart
from engine.market    import get_market_summary
from engine.scanner   import scan_market, _calc_entry_score
from engine.portfolio import buy as port_buy, sell as port_sell, get_positions

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TMPL_DIR   = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TMPL_DIR)


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
    bars   = int(request.args.get("bars", 220))
    try:
        raw_df    = fetch(ticker, period)
        ind_df    = calc_indicators(raw_df)
        fis_df    = calc_fis(ind_df)
        judgment  = make_judgment(fis_df)
        chart_b64 = render_main_chart(fis_df, judgment, ticker, bars)

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
        entry_score = _calc_entry_score(fis_df)

        # ── 추가 지표 계산 ────────────────────────────────────
        c     = float(last["Close"])
        ema20 = float(last.get("EMA20") or 0)
        ema20_gap_pct = round((c - ema20) / ema20 * 100, 2) if ema20 > 0 else 0.0

        bb_up = float(last.get("BB_UP") or 0)
        bb_dn = float(last.get("BB_DN") or 0)
        bb_pos = round((c - bb_dn) / (bb_up - bb_dn) * 100, 1) if (bb_up - bb_dn) > 0 else 50.0

        h52 = float(last.get("High52") or 0)
        l52 = float(last.get("Low52")  or 0)
        pos52 = round((c - l52) / (h52 - l52) * 100, 1) if (h52 - l52) > 0 else 50.0

        pullback_5d = 0.0
        if len(fis_df) >= 6:
            recent_high = float(fis_df.iloc[-6:-1]["High"].max())
            if recent_high > 0:
                pullback_5d = round((recent_high - c) / recent_high * 100, 2)

        prev_close = float(fis_df.iloc[-2]["Close"]) if len(fis_df) >= 2 else c
        day_change_pct = round((c - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0.0
        day_change_abs = round(c - prev_close, 4)

        return jsonify({
            "ok": True, "ticker": ticker, "info": info,
            "judgment": judgment, "chart": chart_b64, "table": table,
            "entry_score": round(entry_score, 1),
            "latest": {
                "close":         c,
                "fis":           float(last["FIS"]),
                "rsi":           float(last.get("RSI14") or 0),
                "rvol":          float(last.get("RVOL")  or 1),
                "atr":           float(last.get("ATR14") or 0),
                "ema20_gap_pct": ema20_gap_pct,
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
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API: 매수 ─────────────────────────────────────────────

@app.route("/api/portfolio/buy", methods=["POST"])
def api_buy():
    body = request.get_json(silent=True) or {}
    ticker = body.get("ticker", "").strip().upper()
    name   = body.get("name", ticker)
    qty    = int(body.get("qty", 0))
    price  = float(body.get("price", 0))
    if not ticker:
        return jsonify({"ok": False, "error": "ticker 필요"}), 400
    try:
        result = port_buy(ticker, name, qty, price)
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
