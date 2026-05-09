"""
engine/market.py
한국/미국 시장 지수 요약 데이터 수집 + 마켓맵 + 52주 신고가
"""

import concurrent.futures
import numpy as np
from engine.data import fetch_market_index, fetch, resample_ohlcv

INDICES = {
    "KR": [
        {"ticker": "^KS11",  "name": "KOSPI",   "flag": "🇰🇷"},
        {"ticker": "^KQ11",  "name": "KOSDAQ",  "flag": "🇰🇷"},
        {"ticker": "KRW=X",  "name": "USD/KRW", "flag": "💱"},
    ],
    "US": [
        {"ticker": "^GSPC",  "name": "S&P 500", "flag": "🇺🇸"},
        {"ticker": "^IXIC",  "name": "NASDAQ",  "flag": "🇺🇸"},
        {"ticker": "^DJI",   "name": "DOW",     "flag": "🇺🇸"},
        {"ticker": "^VIX",   "name": "VIX",     "flag": "😨"},
        {"ticker": "GC=F",   "name": "Gold",    "flag": "🥇"},
        {"ticker": "CL=F",   "name": "WTI",     "flag": "🛢️"},
    ],
}


def get_market_summary() -> dict:
    """전 시장 지수 현황 딕셔너리 반환"""
    result = {"KR": [], "US": []}
    for region, items in INDICES.items():
        for item in items:
            info = fetch_market_index(item["ticker"])
            result[region].append({**item, **info})
    return result


# ── 마켓맵 ────────────────────────────────────────────────

def _fetch_change_one(ticker_name):
    ticker, name = ticker_name
    try:
        import yfinance as yf
        raw = yf.download(ticker, period="5d", auto_adjust=True, progress=False)
        if raw.empty:
            return None
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        close = raw["Close"].dropna()
        if len(close) < 2:
            return None
        price = float(close.iloc[-1])
        prev  = float(close.iloc[-2])
        pct   = (price - prev) / prev * 100 if prev else 0.0
        # short display name
        short = name.replace("홀딩스","").replace("전자","").replace(" Inc.","").replace(" Corp.","")
        short = short[:7]
        return {
            "ticker":     ticker,
            "name":       name,
            "short":      short,
            "price":      round(price, 2),
            "change_pct": round(pct, 2),
        }
    except Exception:
        return None


def get_market_map_data(region: str) -> list:
    """히트맵용 일간 등락률 데이터"""
    from engine.scanner import KOSPI, KOSDAQ, US
    stocks_map = {"KR": KOSPI + KOSDAQ, "US": US}
    stocks = stocks_map.get(region.upper(), [])
    if not stocks:
        return []
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(_fetch_change_one, stocks):
            if r:
                results.append(r)
    results.sort(key=lambda x: x["change_pct"], reverse=True)
    return results


# ── 52주 신고가 ───────────────────────────────────────────

def _check_52w(ticker_name):
    ticker, name = ticker_name
    try:
        df   = fetch(ticker, "2y")
        df_w = resample_ohlcv(df, "weekly")
        if len(df_w) < 20:
            return None
        close  = df_w["Close"]
        high52 = close.rolling(52, min_periods=20).max()
        # 현재 종가가 52주 고점의 98.5% 이상이면 신고가로 판단
        at_high = close >= high52 * 0.985
        if not at_high.iloc[-1]:
            return None
        # 연속 주수 계산
        streak = 0
        for val in reversed(at_high.values.tolist()):
            if val:
                streak += 1
            else:
                break
        current = float(close.iloc[-1])
        h52     = float(high52.iloc[-1])
        gap_pct = (current - h52) / h52 * 100 if h52 else 0.0
        # 일봉 당일 등락
        df_d     = fetch(ticker, "5d")
        dc = df_d["Close"].dropna()
        day_pct  = 0.0
        if len(dc) >= 2:
            day_pct = (float(dc.iloc[-1]) - float(dc.iloc[-2])) / float(dc.iloc[-2]) * 100
        return {
            "ticker":   ticker,
            "name":     name,
            "close":    current,
            "high52":   round(h52, 2),
            "gap_pct":  round(gap_pct, 2),
            "streak":   streak,
            "day_pct":  round(day_pct, 2),
        }
    except Exception:
        return None


def get_52week_highs(market_key: str) -> list:
    """지정 시장의 52주 신고가 종목 반환"""
    from engine.scanner import MARKET_MAP
    stocks = MARKET_MAP.get(market_key.lower(), [])
    if not stocks:
        return []
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(_check_52w, stocks):
            if r:
                results.append(r)
    results.sort(key=lambda x: x["streak"], reverse=True)
    return results
