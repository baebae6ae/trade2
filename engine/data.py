"""engine/data.py — 데이터 수집 및 지표 계산"""

import threading
import warnings

import numpy  as np
import pandas as pd
import yfinance as yf
from engine.universe import ALL_STOCKS, NAME_MAP

warnings.filterwarnings("ignore")

_LOCK = threading.Lock()   # yfinance 동시 다운로드 방지

TIMEFRAME_CONFIG = {
    "daily":   {"rule": None,    "label": "일봉", "min_period": "6mo", "range_window": 252},
    "weekly":  {"rule": "W-FRI", "label": "주봉", "min_period": "5y",  "range_window": 104},
    "monthly": {"rule": "ME",   "label": "월봉", "min_period": "10y", "range_window": 60},
    "yearly":  {"rule": "YE",   "label": "년봉", "min_period": "max", "range_window": 12},
}

PERIOD_ORDER = {
    "1mo": 1,
    "3mo": 2,
    "6mo": 3,
    "1y": 4,
    "2y": 5,
    "5y": 6,
    "10y": 7,
    "max": 8,
}


def resolve_display_name(symbol: str, fallback_name: str = "") -> str:
    normalized = (symbol or "").strip().upper()
    fallback = (fallback_name or "").strip()
    if not normalized:
        return fallback
    return NAME_MAP.get(normalized, fallback or normalized)


# ── 1. 데이터 수집 ──────────────────────────────────────────

def fetch(ticker: str, period: str = "2y") -> pd.DataFrame:
    """yfinance로 OHLCV 데이터 수집"""
    with _LOCK:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"데이터 없음: {ticker}")
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    return df


def normalize_timeframe(timeframe: str | None) -> str:
    value = (timeframe or "daily").strip().lower()
    aliases = {
        "d": "daily", "day": "daily", "daily": "daily", "일": "daily", "일봉": "daily",
        "w": "weekly", "week": "weekly", "weekly": "weekly", "주": "weekly", "주봉": "weekly",
        "m": "monthly", "month": "monthly", "monthly": "monthly", "월": "monthly", "월봉": "monthly",
        "y": "yearly", "year": "yearly", "yearly": "yearly", "년": "yearly", "년봉": "yearly",
    }
    return aliases.get(value, "daily")


def resolve_fetch_period(period: str, timeframe: str) -> str:
    timeframe_key = normalize_timeframe(timeframe)
    requested = (period or "2y").strip().lower()
    minimum = TIMEFRAME_CONFIG[timeframe_key]["min_period"]
    if requested not in PERIOD_ORDER:
        requested = "2y"
    if PERIOD_ORDER[requested] >= PERIOD_ORDER[minimum]:
        return requested
    return minimum


def resample_ohlcv(df: pd.DataFrame, timeframe: str = "daily") -> pd.DataFrame:
    timeframe_key = normalize_timeframe(timeframe)
    rule = TIMEFRAME_CONFIG[timeframe_key]["rule"]
    if rule is None:
        return df.copy()
    resampled = pd.DataFrame({
        "Open": df["Open"].resample(rule).first(),
        "High": df["High"].resample(rule).max(),
        "Low": df["Low"].resample(rule).min(),
        "Close": df["Close"].resample(rule).last(),
        "Volume": df["Volume"].resample(rule).sum(),
    })
    return resampled.dropna(subset=["Open", "High", "Low", "Close"])


def fetch_market_index(ticker: str, period: str = "5d") -> dict:
    """시장 지수 현재가/등락 정보"""
    with _LOCK:
        raw = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if raw.empty:
        return {"price": None, "change": None, "change_pct": None, "direction": "neutral"}
    raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
    close = raw["Close"].dropna()
    if len(close) < 2:
        return {"price": float(close.iloc[-1]) if len(close) else None,
                "change": None, "change_pct": None, "direction": "neutral"}
    price  = float(close.iloc[-1])
    prev   = float(close.iloc[-2])
    change = price - prev
    pct    = change / prev * 100 if prev else 0
    return {
        "price":      price,
        "change":     change,
        "change_pct": pct,
        "direction":  "up" if change > 0 else "down" if change < 0 else "neutral",
    }


# ── 2. 지표 계산 ──────────────────────────────────────────

def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _rsi(s: pd.Series, period: int = 14) -> pd.Series:
    delta = s.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"]  - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _adx(df: pd.DataFrame, period: int = 14):
    up_move   = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm   = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx, plus_di, minus_di


def calc_indicators(df: pd.DataFrame, timeframe: str = "daily") -> pd.DataFrame:
    """EMA / ATR / BB / Ichimoku / RVOL / RSI / MACD / ADX 추가"""
    df = df.copy()
    timeframe_key = normalize_timeframe(timeframe)
    range_window = TIMEFRAME_CONFIG[timeframe_key]["range_window"]

    # EMA
    for span in [5, 10, 20, 60, 120]:
        df[f"EMA{span}"] = _ema(df["Close"], span)

    # ATR
    df["ATR14"] = _atr(df, 14)
    df["ATR60"] = _atr(df, 60)

    # Bollinger
    df["BB_MID"] = df["Close"].rolling(20).mean()
    std          = df["Close"].rolling(20).std()
    df["BB_UP"]  = df["BB_MID"] + 2 * std
    df["BB_DN"]  = df["BB_MID"] - 2 * std
    df["BB_width"] = (df["BB_UP"] - df["BB_DN"]) / df["BB_MID"]

    # ADX / DI
    adx, plus_di, minus_di = _adx(df, 14)
    df["ADX14"] = adx
    df["PLUS_DI14"] = plus_di
    df["MINUS_DI14"] = minus_di

    # Ichimoku (9/26/52)
    hi9  = df["High"].rolling(9).max();  lo9  = df["Low"].rolling(9).min()
    hi26 = df["High"].rolling(26).max(); lo26 = df["Low"].rolling(26).min()
    hi52 = df["High"].rolling(52).max(); lo52 = df["Low"].rolling(52).min()
    df["ICH_TENKAN"]  = (hi9  + lo9)  / 2
    df["ICH_KIJUN"]   = (hi26 + lo26) / 2
    df["ICH_SENKOU_A"] = ((df["ICH_TENKAN"] + df["ICH_KIJUN"]) / 2).shift(26)
    df["ICH_SENKOU_B"] = ((hi52 + lo52) / 2).shift(26)
    df["ICH_CHIKOU"]   = df["Close"].shift(-26)

    # Volume
    df["Vol20"] = df["Volume"].rolling(20).mean()
    df["Vol60"] = df["Volume"].rolling(60).mean()
    df["RVOL"]  = df["Volume"] / df["Vol20"].replace(0, np.nan)

    # 장기 위치 범위
    df["RangeHigh"] = df["High"].rolling(range_window, min_periods=max(5, range_window // 4)).max()
    df["RangeLow"]  = df["Low"].rolling(range_window, min_periods=max(5, range_window // 4)).min()
    df["High52"] = df["RangeHigh"]
    df["Low52"]  = df["RangeLow"]

    # RSI14
    df["RSI14"] = _rsi(df["Close"], 14)

    # 가격 변화율
    df["ROC5"]  = df["Close"].pct_change(5) * 100
    df["ROC20"] = df["Close"].pct_change(20) * 100

    # MACD (12/26/9)
    ema12 = _ema(df["Close"], 12)
    ema26 = _ema(df["Close"], 26)
    df["MACD"]      = ema12 - ema26
    df["MACD_SIG"]  = _ema(df["MACD"], 9)
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIG"]

    # 캔들 구조 보조
    spread = (df["High"] - df["Low"]).replace(0, np.nan)
    df["ClosePos"] = ((df["Close"] - df["Low"]) / spread).clip(0, 1)
    df["UpperWickRatio"] = (df["High"] - df[["Open", "Close"]].max(axis=1)) / spread
    df["LowerWickRatio"] = (df[["Open", "Close"]].min(axis=1) - df["Low"]) / spread
    df["BodyPct"] = (df["Close"] - df["Open"]).abs() / spread

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df.dropna(subset=["Open", "High", "Low", "Close"])


# ── 3. 종목 정보 ──────────────────────────────────────────

def get_info(ticker: str) -> dict:
    """종목 기본 정보 (이름/섹터/시총 등)"""
    try:
        info = yf.Ticker(ticker).info
        raw_name = info.get("longName") or info.get("shortName") or ticker
        return {
            "name":       resolve_display_name(ticker, raw_name),
            "sector":     info.get("sector", ""),
            "industry":   info.get("industry", ""),
            "currency":   info.get("currency", ""),
            "exchange":   info.get("exchange", ""),
            "market_cap": info.get("marketCap"),
        }
    except Exception:
        return {"name": resolve_display_name(ticker, ticker), "sector": "", "industry": "",
                "currency": "", "exchange": "", "market_cap": None}


# ── 4. 종목 검색 ──────────────────────────────────────────

def search_ticker(query: str) -> list:
    """
    종목 검색 (한글/영문/ticker 모두 지원)
    
    검색 로직:
      1. ALL_STOCKS에서 먼저 검색 (하드코딩된 우선)
      2. 결과 없거나 부족하면 yfinance 동적 검색
      3. 결과 통합 및 정렬
    """
    q = (query or "").strip()
    if not q:
        return []

    compact = q.replace(" ", "").lower()
    ranked = {}  # symbol -> {name, score} (중복 제거용)
    
    # ─────────────────────────────────────────────
    # Step 1: ALL_STOCKS에서 검색 (하드코딩된 우선)
    # ─────────────────────────────────────────────
    for symbol, name in ALL_STOCKS:
        symbol_u = symbol.upper()
        name_key = name.replace(" ", "").lower()
        symbol_key = symbol.lower()
        
        if compact not in name_key and compact not in symbol_key:
            continue

        score = 0
        # 이름 매칭
        if name == q or name_key == compact:
            score += 100
        elif name.startswith(q):
            score += 60
        elif compact in name_key:
            score += 35

        # Ticker 매칭
        if symbol_key == compact:
            score += 90
        elif symbol_key.startswith(compact):
            score += 25
        elif compact in symbol_key:
            score += 10

        if score > 0:
            ranked[symbol_u] = {"name": name, "score": score}

    # ─────────────────────────────────────────────
    # Step 2: 결과 없으면 yfinance 동적 검색
    # ─────────────────────────────────────────────
    if not ranked:
        try:
            # ticker 직접 조회 (정확히 일치하는 경우)
            ticker_normalized = q.upper()
            if len(ticker_normalized) <= 10:
                symbol, name = _get_from_universe(ticker_normalized)
                if symbol:
                    ranked[symbol] = {"name": name, "score": 80}
        except:
            pass

    # ─────────────────────────────────────────────
    # Step 3: 결과 포맷 및 정렬
    # ─────────────────────────────────────────────
    results = []
    for symbol, data in ranked.items():
        results.append({
            "symbol": symbol,
            "name": data["name"],
            "exchange": "KRX" if symbol.endswith((".KS", ".KQ")) else "US",
            "type": "EQUITY",
            "_score": data["score"],
        })

    results.sort(key=lambda x: (-x["_score"], x["name"], x["symbol"]))
    return [{k: v for k, v in item.items() if k != "_score"} for item in results[:8]]


def _get_from_universe(ticker: str) -> tuple:
    """universe에서 종목 정보 가져오기 (없으면 yfinance에서 동적 로드)"""
    from engine.universe import get_or_fetch_stock_info
    try:
        return get_or_fetch_stock_info(ticker)
    except:
        return None, None
