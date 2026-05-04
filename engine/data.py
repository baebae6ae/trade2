"""engine/data.py — 데이터 수집 및 지표 계산"""

import threading
import warnings

import numpy  as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

_LOCK = threading.Lock()   # yfinance 동시 다운로드 방지


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


def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """EMA / ATR / BB / Ichimoku / RVOL / RSI / MACD 추가"""
    df = df.copy()

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

    # 52주 고저
    df["High52"] = df["High"].rolling(252).max()
    df["Low52"]  = df["Low"].rolling(252).min()

    # RSI14
    df["RSI14"] = _rsi(df["Close"], 14)

    # MACD (12/26/9)
    ema12 = _ema(df["Close"], 12)
    ema26 = _ema(df["Close"], 26)
    df["MACD"]      = ema12 - ema26
    df["MACD_SIG"]  = _ema(df["MACD"], 9)
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIG"]

    df.dropna(subset=["EMA60", "ICH_SENKOU_A"], inplace=True)
    return df


# ── 3. 종목 정보 ──────────────────────────────────────────

def get_info(ticker: str) -> dict:
    """종목 기본 정보 (이름/섹터/시총 등)"""
    try:
        info = yf.Ticker(ticker).info
        return {
            "name":       info.get("longName") or info.get("shortName") or ticker,
            "sector":     info.get("sector", ""),
            "industry":   info.get("industry", ""),
            "currency":   info.get("currency", ""),
            "exchange":   info.get("exchange", ""),
            "market_cap": info.get("marketCap"),
        }
    except Exception:
        return {"name": ticker, "sector": "", "industry": "",
                "currency": "", "exchange": "", "market_cap": None}


# ── 4. 종목 검색 ──────────────────────────────────────────

def search_ticker(query: str) -> list:
    """yfinance 검색 → [{symbol, name, exchange, type}, ...]"""
    try:
        results = yf.Search(query, max_results=8).quotes
        out = []
        for r in results:
            out.append({
                "symbol":   r.get("symbol", ""),
                "name":     r.get("longname") or r.get("shortname") or "",
                "exchange": r.get("exchange", ""),
                "type":     r.get("quoteType", ""),
            })
        return out
    except Exception:
        return []
