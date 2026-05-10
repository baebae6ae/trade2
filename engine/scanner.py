"""engine/scanner.py — 신규 진입 후보 종목 스캐너"""

import concurrent.futures
import numpy as np
from engine.data import fetch, calc_indicators
from engine.fis  import calc_fis, make_judgment, calc_entry_score
from engine.universe import get_market_stocks


def _analyze_one(ticker_name):
    ticker, name = ticker_name
    try:
        df     = fetch(ticker, "1y")
        df     = calc_indicators(df, mode="fis")
        df_fis = calc_fis(df)
        j      = make_judgment(df_fis)
        last        = df_fis.iloc[-1]
        entry_data  = calc_entry_score(df_fis)
        entry_score = float(entry_data["score"])
        close_v     = float(last["Close"])
        ema20_v     = float(last.get("EMA20", close_v))
        atr_v       = float(last.get("ATR14") or 0)
        high20_v    = float(df_fis["High"].iloc[-20:].max()) if len(df_fis) >= 20 else float(df_fis["High"].max())
        ema20_gap   = round((close_v - ema20_v) / ema20_v * 100, 1) if ema20_v > 0 else 0.0
        return {
            "ticker":       ticker,
            "name":         name,
            "fis":          j["fis"],
            "label":        j["label"],
            "label_color":  j["label_color"],
            "close":        close_v,
            "trend":        float(last["TrendScore"]),
            "momentum":     float(last["MomentumScore"]),
            "structure":    float(last["StructureScore"]),
            "compression":  float(last["CompressionScore"]),
            "volume":       float(last["VolumeScore"]),
            "risk":         float(last["RiskPenalty"]),
            "entry_score":        entry_score,
            "entry_setup_name":   entry_data["setup_name"],
            "entry_setup_name2":  entry_data.get("setup_name2", ""),
            "entry_components":   entry_data["components"],
            "entry_setup_scores": entry_data["setup_scores"],
            "entry_metrics":      entry_data["metrics"],
            "ema20_gap":          ema20_gap,
            "atr":                atr_v,
            "high20":             high20_v,
            "ichimoku":     j["ichimoku_status"],
            "summary_l1":   j["summary_l1"],
            "ok": True,
        }
    except Exception as e:
        return {"ticker": ticker, "name": name, "ok": False, "error": str(e)}


def _analyze_batch(stocks: list) -> list:
    if not stocks:
        return []
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(_analyze_one, stocks):
            if r.get("ok"):
                results.append(r)
    return results


def scan_market(market: str, offset: int = 0, limit: int = 10) -> tuple[list, int]:
    """
    지정 시장 전체 스캔 -> 신규 진입 후보

        필터:
            FIS ≥ 30 AND entry_score ≥ 55 AND risk > -16 AND trend > 0
            → '상승 우위가 유지되면서 눌림 품질이 양호한 종목'

    정렬: entry_score 높은 순 (눌림 품질 우선)
    """
    size = max(1, int(limit or 10))
    cursor = max(0, int(offset or 0))
    candidates = []

    while len(candidates) < size:
        batch = get_market_stocks(market, offset=cursor, limit=size)
        if not batch:
            break

        results = _analyze_batch(batch)
        filtered = [
            r for r in results
            if r["fis"] >= 30
            and r["entry_score"] >= 55
            and r["risk"] > -16
            and r["trend"] > 0
        ]
        candidates.extend(filtered)
        cursor += len(batch)

    candidates = candidates[:size]
    candidates.sort(key=lambda x: x["entry_score"], reverse=True)
    return candidates, cursor


# ── 쿠모 브레이크아웃 스캐너 ────────────────────────────────

def _calc_ichimoku_raw(df):
    """일목균형표 (shift 없이 현재 가격 기준)"""
    df = df.copy()
    hi9  = df["High"].rolling(9,  min_periods=9).max()
    lo9  = df["Low"].rolling(9,   min_periods=9).min()
    hi26 = df["High"].rolling(26, min_periods=26).max()
    lo26 = df["Low"].rolling(26,  min_periods=26).min()
    hi52 = df["High"].rolling(52, min_periods=52).max()
    lo52 = df["Low"].rolling(52,  min_periods=52).min()
    df["tenkan"]    = (hi9 + lo9) / 2
    df["kijun"]     = (hi26 + lo26) / 2
    df["cloud_a"]   = (df["tenkan"] + df["kijun"]) / 2
    df["cloud_b"]   = (hi52 + lo52) / 2
    df["above_c"]   = (df["Close"] > df[["cloud_a","cloud_b"]].max(axis=1)).astype(int)
    df["below_c"]   = (df["Close"] < df[["cloud_a","cloud_b"]].min(axis=1)).astype(int)
    df["bull_cloud"]= (df["cloud_a"] >= df["cloud_b"]).astype(int)
    df["c_thick"]   = (df["cloud_a"] - df["cloud_b"]).abs() / df["Close"].replace(0, np.nan)
    return df.dropna(subset=["cloud_a", "cloud_b"])


def _kumo_check_one(ticker_name):
    ticker, name = ticker_name
    try:
        from engine.data import fetch, resample_ohlcv

        # 일봉 (최근 2년)
        df_d = fetch(ticker, "2y")
        df_d["vol20"] = df_d["Volume"].rolling(20).mean()

        # 주봉 변환 + 일목 계산
        df_w = resample_ohlcv(df_d, "weekly")
        if len(df_w) < 60:
            return {"ticker": ticker, "name": name, "ok": False}
        df_w = _calc_ichimoku_raw(df_w)
        if len(df_w) < 40:
            return {"ticker": ticker, "name": name, "ok": False}

        above = df_w["above_c"].values
        below = df_w["below_c"].values
        bull  = df_w["bull_cloud"].values
        thick = df_w["c_thick"].values
        n     = len(df_w)

        # ── 조건 1: 현재 구름 위 ──
        if above[-1] != 1:
            return {"ticker": ticker, "name": name, "ok": False}

        # ── 조건 2: 최근 4~16주 내에 구름 돌파 시점 찾기 ──
        brk_idx = None
        for i in range(n - 36, n):
            if i < 1:
                continue
            if above[i] == 1 and above[i-1] != 1:
                brk_idx = i
        if brk_idx is None:
            return {"ticker": ticker, "name": name, "ok": False}

        # ── 조건 3: 돌파 전 50주 중 누적 구름 아래 10주 이상 ──
        look_back = slice(max(0, brk_idx - 50), brk_idx)
        below_cnt = int(__import__('numpy').sum(below[look_back]))
        if below_cnt < 10:
            return {"ticker": ticker, "name": name, "ok": False}

        # ── 조건 4: 구름 반전(Kumo Twist) ─ 돌파 ±8주 내 ──
        rng = slice(max(0, brk_idx - 8), min(n, brk_idx + 8))
        bull_slice = bull[rng]
        had_twist = any(
            bull_slice[j] == 1 and (j == 0 or bull_slice[j-1] == 0)
            for j in range(len(bull_slice))
        )
        if not (had_twist or bull[-1] == 1):
            return {"ticker": ticker, "name": name, "ok": False}

        # ── 조건 5: 돌파 전 구름 두께 ──
        thin_slice = thick[max(0, brk_idx - 6): brk_idx + 2]
        min_thick  = float(np.nanmin(thin_slice)) * 100 if len(thin_slice) else 99.0

        # ── 조건 6: 일봉 거래량 폭발 + 장대양봉 (최근 25일) ──
        recent_d = df_d.iloc[-25:]
        big_candle = False
        for _, row in recent_d.iterrows():
            v20 = row.get("vol20", 0)
            if not v20 or row["Volume"] < v20 * 1.8:
                continue
            body = row["Close"] - row["Open"]
            rng_v = row["High"] - row["Low"]
            if body > 0 and (rng_v == 0 or body / rng_v > 0.25):
                big_candle = True
                break

        close_v = float(df_w.iloc[-1]["Close"])
        return {
            "ticker":      ticker,
            "name":        name,
            "ok":          True,
            "below_weeks": int(below_cnt),
            "cloud_thin":  round(min_thick, 1),
            "bull_cloud":  bool(bull[-1] == 1),
            "daily_vol":   big_candle,
            "had_twist":  bool(had_twist),
            "close":       close_v,
        }
    except Exception as e:
        return {"ticker": ticker, "name": name, "ok": False, "error": str(e)}


def scan_kumo_breakout(market: str, offset: int = 0, limit: int = 10) -> tuple[list, int]:
    """
    쿠모 브레이크아웃 패턴 스캔 (주봉 기준)
      - 구름 아래 20주+ 체류 후 구름 돌파
      - 구름 반전(Kumo Twist) 동반
      - 일봉 거래량 폭발 + 장대양봉
    """
    size = max(1, int(limit or 10))
    cursor = max(0, int(offset or 0))
    collected = []

    while len(collected) < size:
        batch = get_market_stocks(market, offset=cursor, limit=size)
        if not batch:
            break

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            for r in ex.map(_kumo_check_one, batch):
                if r.get("ok"):
                    collected.append(r)
        cursor += len(batch)

    collected = collected[:size]
    collected.sort(key=lambda x: x.get("below_weeks", 0), reverse=True)
    return collected, cursor



