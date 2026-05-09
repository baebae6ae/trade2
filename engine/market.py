"""
engine/market.py
한국/미국 시장 지수 + 마켓맵 (배치) + 52주 신고가 (배치)
"""

import concurrent.futures
import numpy as np
import pandas as pd
import yfinance as yf
from engine.data import fetch_market_index, resample_ohlcv

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

# ── 섹터 구조 정의 ─────────────────────────────────────────
# KR 섹터: (섹터명, [(ticker, name), ...])
KR_SECTORS = [
    ("반도체", [("005930.KS","삼성전자"),("000660.KS","SK하이닉스"),("009150.KS","삼성전기"),("034220.KS","LG디스플레이")]),
    ("자동차", [("005380.KS","현대차"),("000270.KS","기아"),("012330.KS","현대모비스"),("247540.KQ","에코프로비엠")]),
    ("화학·배터리", [("051910.KS","LG화학"),("006400.KS","삼성SDI"),("096770.KS","SK이노베이션"),("066970.KQ","엘앤에프")]),
    ("금융", [("055550.KS","신한지주"),("086790.KS","하나금융지주"),("024110.KS","기업은행"),("316140.KS","우리금융지주"),("032830.KS","삼성생명"),("000810.KS","삼성화재")]),
    ("IT·플랫폼", [("035420.KS","NAVER"),("035720.KS","카카오"),("018260.KS","삼성SDS"),("017670.KS","SK텔레콤")]),
    ("에너지", [("010950.KS","S-Oil"),("015760.KS","한국전력")]),
    ("소재·산업재", [("005490.KS","POSCO홀딩스"),("028260.KS","삼성물산"),("003550.KS","LG"),("011200.KS","HMM"),("003490.KS","대한항공")]),
    ("바이오·헬스", [("207940.KS","삼성바이오로직스"),("033780.KS","KT&G"),("145020.KQ","휴젤"),("196170.KQ","알테오젠"),("285130.KQ","SK바이오사이언스")]),
    ("게임·엔터", [("263750.KQ","펄어비스"),("041510.KQ","에스엠"),("293480.KQ","카카오게임즈"),("035900.KQ","JYP Ent."),("112040.KQ","위메이드"),("251270.KQ","넷마블")]),
    ("소부장", [("357780.KQ","솔브레인"),("394280.KQ","오픈엣지테크놀로지"),("140860.KQ","파크시스템스"),("095340.KQ","ISC"),("211270.KQ","AP시스템"),("039030.KQ","이오테크닉스")]),
]

US_SECTORS = [
    ("Tech", [("AAPL","Apple"),("MSFT","Microsoft"),("NVDA","NVIDIA"),("AVGO","Broadcom"),("ORCL","Oracle"),("AMD","AMD"),("INTC","Intel"),("CRM","Salesforce")]),
    ("Communication", [("GOOGL","Alphabet"),("META","Meta"),("NFLX","Netflix"),("DIS","Disney")]),
    ("Consumer", [("AMZN","Amazon"),("TSLA","Tesla"),("HD","Home Depot"),("COST","Costco"),("WMT","Walmart"),("KO","Coca-Cola"),("PEP","PepsiCo")]),
    ("Finance", [("JPM","JPMorgan"),("V","Visa"),("MA","Mastercard"),("BAC","Bank of America")]),
    ("Healthcare", [("UNH","UnitedHealth"),("LLY","Eli Lilly"),("JNJ","J&J"),("ABBV","AbbVie"),("MRK","Merck")]),
    ("Energy", [("XOM","Exxon")]),
]

# 섹터 → ticker 역매핑
def _build_ticker_to_sector(sectors):
    mapping = {}
    for sector, stocks in sectors:
        for ticker, name in stocks:
            mapping[ticker] = sector
    return mapping

KR_TICKER_SECTOR = _build_ticker_to_sector(KR_SECTORS)
US_TICKER_SECTOR = _build_ticker_to_sector(US_SECTORS)


def get_market_summary() -> dict:
    result = {"KR": [], "US": []}
    for region, items in INDICES.items():
        for item in items:
            info = fetch_market_index(item["ticker"])
            result[region].append({**item, **info})
    return result


# ── 배치 다운로드 ─────────────────────────────────────────

def _batch_change(tickers: list) -> dict:
    """
    yfinance 배치 다운로드로 일간 등락률 한번에 계산.
    반환: {ticker: change_pct}
    """
    if not tickers:
        return {}
    try:
        raw = yf.download(
            tickers, period="5d",
            auto_adjust=True, progress=False,
            group_by="ticker", threads=True,
        )
        result = {}
        if len(tickers) == 1:
            ticker = tickers[0]
            close = raw["Close"].dropna() if "Close" in raw.columns else pd.Series()
            if len(close) >= 2:
                result[ticker] = round((float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2)
            return result

        for ticker in tickers:
            try:
                if ticker not in raw.columns.get_level_values(0):
                    continue
                close = raw[ticker]["Close"].dropna()
                if len(close) < 2:
                    continue
                result[ticker] = round((float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2)
            except Exception:
                continue
        return result
    except Exception:
        return {}


def _batch_prices(tickers: list) -> dict:
    """배치로 최신 종가 반환: {ticker: price}"""
    if not tickers:
        return {}
    try:
        raw = yf.download(
            tickers, period="5d",
            auto_adjust=True, progress=False,
            group_by="ticker", threads=True,
        )
        result = {}
        if len(tickers) == 1:
            ticker = tickers[0]
            close = raw["Close"].dropna() if "Close" in raw.columns else pd.Series()
            if len(close):
                result[ticker] = float(close.iloc[-1])
            return result
        for ticker in tickers:
            try:
                close = raw[ticker]["Close"].dropna()
                if len(close):
                    result[ticker] = float(close.iloc[-1])
            except Exception:
                continue
        return result
    except Exception:
        return {}


# ── 마켓맵 데이터 ─────────────────────────────────────────

def get_market_map_data(region: str) -> dict:
    """
    트리맵용 데이터 반환.
    {
      "stocks": [{ticker, name, short, change_pct, sector}, ...],
      "sectors": [{name, change_pct, stocks:[...]}, ...]
    }
    """
    if region.upper() == "KR":
        sectors_def    = KR_SECTORS
        ticker_sector  = KR_TICKER_SECTOR
    else:
        sectors_def    = US_SECTORS
        ticker_sector  = US_TICKER_SECTOR

    all_stocks = [(t, n) for _, pairs in sectors_def for t, n in pairs]
    all_tickers = [t for t, _ in all_stocks]
    name_map    = {t: n for t, n in all_stocks}

    changes = _batch_change(all_tickers)

    stocks_out = []
    for ticker, name in all_stocks:
        pct   = changes.get(ticker, 0.0)
        short = (name.replace("홀딩스","").replace("전자","")
                     .replace(" Inc.","").replace(" Corp.",""))[:8]
        stocks_out.append({
            "ticker":     ticker,
            "name":       name,
            "short":      short,
            "change_pct": pct,
            "sector":     ticker_sector.get(ticker, "기타"),
        })

    # 섹터별 집계 (단순 평균)
    sectors_out = []
    for sector_name, pairs in sectors_def:
        s_tickers = [t for t, _ in pairs]
        pcts = [changes[t] for t in s_tickers if t in changes]
        avg  = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
        sectors_out.append({
            "name":       sector_name,
            "change_pct": avg,
            "count":      len(pairs),
        })

    return {"stocks": stocks_out, "sectors": sectors_out}


# ── 52주 신고가 (배치) ────────────────────────────────────

def get_52week_highs(market_key: str) -> list:
    from engine.scanner import MARKET_MAP

    stocks = MARKET_MAP.get(market_key.lower(), [])
    if not stocks:
        return []

    all_tickers = [t for t, _ in stocks]
    name_map    = {t: n for t, n in stocks}

    # 2년치 주봉 데이터 배치 다운로드
    try:
        raw_daily = yf.download(
            all_tickers, period="2y",
            auto_adjust=True, progress=False,
            group_by="ticker", threads=True,
        )
    except Exception:
        return []

    results = []
    for ticker in all_tickers:
        name = name_map[ticker]
        try:
            if len(all_tickers) == 1:
                close_d = raw_daily["Close"].dropna()
            else:
                if ticker not in raw_daily.columns.get_level_values(0):
                    continue
                close_d = raw_daily[ticker]["Close"].dropna()
            if len(close_d) < 20:
                continue

            close_w = close_d.resample("W-FRI").last().dropna()
            if len(close_w) < 10:
                continue

            high52  = close_w.rolling(52, min_periods=10).max()
            at_high = close_w >= high52 * 0.985
            if not at_high.iloc[-1]:
                continue

            streak = 0
            for val in reversed(at_high.values.tolist()):
                if val:
                    streak += 1
                else:
                    break

            current = float(close_w.iloc[-1])
            h52     = float(high52.iloc[-1])
            gap_pct = round((current - h52) / h52 * 100, 2) if h52 else 0.0

            # 당일 등락 (일봉 마지막 2개)
            day_pct = 0.0
            if len(close_d) >= 2:
                day_pct = round((float(close_d.iloc[-1]) - float(close_d.iloc[-2])) / float(close_d.iloc[-2]) * 100, 2)

            results.append({
                "ticker":  ticker,
                "name":    name,
                "close":   round(current, 2),
                "high52":  round(h52, 2),
                "gap_pct": gap_pct,
                "streak":  streak,
                "day_pct": day_pct,
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["streak"], reverse=True)
    return results
