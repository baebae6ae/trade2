"""engine/universe.py — KRX/US 종목 유니버스

KRX(KOSPI/KOSDAQ)는 FinanceDataReader에서 자동 로드해
오타/누락 없는 전체 시장 분석 기반을 제공한다.
"""

import json
import os
from typing import Dict, List, Tuple

import yfinance as yf

try:
    import FinanceDataReader as fdr
except Exception:
    fdr = None


US_BASE = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta",
    "TSLA": "Tesla",
    "AVGO": "Broadcom",
    "JPM": "JPMorgan Chase",
    "LLY": "Eli Lilly",
    "V": "Visa",
    "UNH": "UnitedHealth",
    "XOM": "Exxon Mobil",
    "MA": "Mastercard",
    "JNJ": "Johnson & Johnson",
    "PG": "Procter & Gamble",
    "HD": "Home Depot",
    "COST": "Costco",
    "WMT": "Walmart",
    "BAC": "Bank of America",
    "CRM": "Salesforce",
    "ORCL": "Oracle",
    "NFLX": "Netflix",
    "AMD": "AMD",
    "INTC": "Intel",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
    "DIS": "Disney",
    "ABBV": "AbbVie",
    "MRK": "Merck",
}

FALLBACK_KOSPI = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "005380.KS": "현대차",
    "000270.KS": "기아",
    "051910.KS": "LG화학",
    "006400.KS": "삼성SDI",
    "012330.KS": "현대모비스",
    "207940.KS": "삼성바이오로직스",
    "035420.KS": "NAVER",
    "035720.KS": "카카오",
}

FALLBACK_KOSDAQ = {
    "247540.KQ": "에코프로비엠",
    "086520.KQ": "에코프로",
    "263750.KQ": "펄어비스",
    "293490.KQ": "카카오게임즈",
    "196170.KQ": "알테오젠",
}


def _cache_path() -> str:
    return os.path.join(os.path.dirname(__file__), "_krx_universe_cache.json")


def _load_krx_from_cache():
    path = _cache_path()
    if not os.path.exists(path):
        return [], [], [], []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        kospi = [(s, n) for s, n in payload.get('kospi', []) if s and n]
        kosdaq = [(s, n) for s, n in payload.get('kosdaq', []) if s and n]
        kospi_r = [(s, n) for s, n in payload.get('kospi_ranked', [])] or kospi
        kosdaq_r = [(s, n) for s, n in payload.get('kosdaq_ranked', [])] or kosdaq
        return kospi, kosdaq, kospi_r, kosdaq_r
    except Exception:
        return [], [], [], []


def _save_krx_cache(kospi, kosdaq, kospi_ranked, kosdaq_ranked):
    path = _cache_path()
    payload = {'kospi': kospi, 'kosdaq': kosdaq, 'kospi_ranked': kospi_ranked, 'kosdaq_ranked': kosdaq_ranked}
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass


def _normalize_code(value: str) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        return ""
    return text.zfill(6)


def _to_float(value) -> float:
    try:
        if value is None:
            return 0.0
        text = str(value).replace(",", "").strip()
        if not text:
            return 0.0
        return float(text)
    except Exception:
        return 0.0


def _build_krx_universe_from_fdr() -> Tuple[
    List[Tuple[str, str]],
    List[Tuple[str, str]],
    List[Tuple[str, str]],
    List[Tuple[str, str]],
]:
    if fdr is None:
        raise RuntimeError("FinanceDataReader is not available")

    listing = fdr.StockListing("KRX")
    if listing is None or listing.empty:
        raise RuntimeError("KRX listing is empty")

    cols = ["Code", "Name", "Market"]
    if "Marcap" in listing.columns:
        cols.append("Marcap")
    rows = listing[cols].dropna(subset=["Code", "Name", "Market"])

    kospi_map: Dict[str, str] = {}
    kosdaq_map: Dict[str, str] = {}
    kospi_caps: Dict[str, float] = {}
    kosdaq_caps: Dict[str, float] = {}

    for _, row in rows.iterrows():
        code = _normalize_code(row["Code"])
        name = str(row["Name"] or "").strip()
        market = str(row["Market"] or "").strip().upper()
        if not code or not name:
            continue

        marcap = _to_float(row.get("Marcap") if hasattr(row, "get") else None)

        if market.startswith("KOSPI"):
            symbol = f"{code}.KS"
            kospi_map[symbol] = name
            kospi_caps[symbol] = marcap
        elif market.startswith("KOSDAQ"):
            symbol = f"{code}.KQ"
            kosdaq_map[symbol] = name
            kosdaq_caps[symbol] = marcap

    kospi = sorted(kospi_map.items(), key=lambda x: x[0])
    kosdaq = sorted(kosdaq_map.items(), key=lambda x: x[0])
    if not kospi and not kosdaq:
        raise RuntimeError("No KOSPI/KOSDAQ symbols found from FDR")

    kospi_ranked = sorted(
        [(symbol, kospi_map[symbol]) for symbol in kospi_map],
        key=lambda x: (-kospi_caps.get(x[0], 0.0), x[0]),
    )
    kosdaq_ranked = sorted(
        [(symbol, kosdaq_map[symbol]) for symbol in kosdaq_map],
        key=lambda x: (-kosdaq_caps.get(x[0], 0.0), x[0]),
    )
    return kospi, kosdaq, kospi_ranked, kosdaq_ranked


def _load_krx_universe() -> Tuple[
    List[Tuple[str, str]],
    List[Tuple[str, str]],
    List[Tuple[str, str]],
    List[Tuple[str, str]],
    str,
]:
    try:
        kospi, kosdaq, kospi_ranked, kosdaq_ranked = _build_krx_universe_from_fdr()
        _save_krx_cache(kospi, kosdaq, kospi_ranked, kosdaq_ranked)
        return kospi, kosdaq, kospi_ranked, kosdaq_ranked, "fdr"
    except Exception:
        cached_kospi, cached_kosdaq, cached_kospi_r, cached_kosdaq_r = _load_krx_from_cache()
        if cached_kospi or cached_kosdaq:
            return cached_kospi, cached_kosdaq, cached_kospi_r, cached_kosdaq_r, "cache"
        fb_kospi = sorted(FALLBACK_KOSPI.items(), key=lambda x: x[0])
        fb_kosdaq = sorted(FALLBACK_KOSDAQ.items(), key=lambda x: x[0])
        return (
            fb_kospi,
            fb_kosdaq,
            fb_kospi,
            fb_kosdaq,
            "fallback",
        )


def _get_display_name(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName") or ticker
    except Exception:
        return ticker


KOSPI, KOSDAQ, KOSPI_CAP_RANKED, KOSDAQ_CAP_RANKED, KRX_SOURCE = _load_krx_universe()
US = sorted(US_BASE.items(), key=lambda x: x[0])

ALL_STOCKS = KOSPI + KOSDAQ + US
NAME_MAP = {ticker: name for ticker, name in ALL_STOCKS}
TICKER_MAP = {ticker.upper(): ticker for ticker, _ in ALL_STOCKS}
KRX_CODE_MAP = {
    ticker.split(".")[0]: ticker
    for ticker, _ in (KOSPI + KOSDAQ)
}

MARKET_MAP = {
    "kospi": KOSPI,
    "kosdaq": KOSDAQ,
    "us": US,
}

MARKET_CAP_RANK_MAP = {
    "kospi": KOSPI_CAP_RANKED,
    "kosdaq": KOSDAQ_CAP_RANKED,
    "us": US,
}

_CACHE: Dict[str, Tuple[str, str]] = {}


def get_or_fetch_stock_info(ticker: str) -> Tuple[str, str]:
    """주어진 ticker에 대해 (symbol, name) 반환."""
    raw = (ticker or "").strip()
    if not raw:
        return "", ""

    ticker_upper = raw.upper()

    canonical = TICKER_MAP.get(ticker_upper)
    if canonical:
        return canonical, NAME_MAP.get(canonical, canonical)

    if ticker_upper.isdigit() and len(ticker_upper) == 6:
        krx_symbol = KRX_CODE_MAP.get(ticker_upper)
        if krx_symbol:
            return krx_symbol, NAME_MAP.get(krx_symbol, krx_symbol)

    if ticker_upper in _CACHE:
        return _CACHE[ticker_upper]

    try:
        info = yf.Ticker(raw).info
        name = info.get("longName") or info.get("shortName") or raw
        payload = (ticker_upper, name)
        _CACHE[ticker_upper] = payload
        return payload
    except Exception:
        payload = (ticker_upper, raw)
        _CACHE[ticker_upper] = payload
        return payload


def get_market_stocks(market: str, offset: int = 0, limit: int | None = None) -> List[Tuple[str, str]]:
    """시장별 종목을 시총 순(가능 시)으로 반환하고 offset/limit를 적용한다."""
    market_key = (market or "").strip().lower()
    stocks = MARKET_CAP_RANK_MAP.get(market_key, MARKET_MAP.get(market_key, []))
    if not stocks:
        return []

    start = max(0, int(offset or 0))
    if limit is None:
        return stocks[start:]

    size = max(1, int(limit))
    end = start + size
    return stocks[start:end]


def get_market_total_count(market: str) -> int:
    market_key = (market or "").strip().lower()
    stocks = MARKET_CAP_RANK_MAP.get(market_key, MARKET_MAP.get(market_key, []))
    return len(stocks)


print(
    f"✅ Universe loaded ({KRX_SOURCE}): "
    f"KOSPI={len(KOSPI)}, KOSDAQ={len(KOSDAQ)}, US={len(US)}, Total={len(ALL_STOCKS)}"
)
