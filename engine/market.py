"""
engine/market.py
한국/미국 시장 지수 요약 데이터 수집
"""

from engine.data import fetch_market_index

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
