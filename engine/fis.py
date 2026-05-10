"""engine/fis.py — FIS(First Impression Score)와 진입 점수 계산"""

import numpy as np
import pandas as pd


def _fnum(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _clip(value: float, low: float, high: float) -> float:
    return float(np.clip(value, low, high))


def _range_pos(close: float, low: float, high: float, default: float = 0.5) -> float:
    if high <= low:
        return default
    return _clip((close - low) / (high - low), 0.0, 1.0)


def _cloud_status(row: pd.Series) -> tuple[str, int]:
    cloud_a = _fnum(row.get("ICH_SENKOU_A"), np.nan)
    cloud_b = _fnum(row.get("ICH_SENKOU_B"), np.nan)
    close = _fnum(row.get("Close"))
    if np.isnan(cloud_a) or np.isnan(cloud_b):
        return "구름 정보 부족", 0
    top = max(cloud_a, cloud_b)
    bottom = min(cloud_a, cloud_b)
    if close > top:
        return "구름 위 — 매수 우세", 1
    if close < bottom:
        return "구름 아래 — 매도 우세", -1
    return "구름 내부 — 중립", 0


def score_trend(df: pd.DataFrame, idx: int) -> float:
    row = df.iloc[idx]
    close = _fnum(row.get("Close"))
    ema20 = _fnum(row.get("EMA20"), close)
    ema60 = _fnum(row.get("EMA60"), close)
    ema120 = _fnum(row.get("EMA120"), close)
    score = 0.0

    score += 6 if close >= ema20 else -6
    score += 7 if close >= ema60 else -7
    score += 6 if ema20 >= ema60 else -6
    score += 5 if ema60 >= ema120 else -5

    if idx >= 8:
        score += 3 if ema20 >= _fnum(df.iloc[idx - 8].get("EMA20"), ema20) else -3

    adx = _fnum(row.get("ADX14"), 18)
    plus_di = _fnum(row.get("PLUS_DI14"), 0)
    minus_di = _fnum(row.get("MINUS_DI14"), 0)
    if adx >= 22:
        score += 3 if plus_di >= minus_di else -3
    elif adx < 15:
        score -= 1 if abs(close - ema20) < max(_fnum(row.get("ATR14"), 0), close * 0.005) else 0

    return _clip(score, -30, 30)


def score_momentum(df: pd.DataFrame, idx: int) -> float:
    row = df.iloc[idx]
    close = _fnum(row.get("Close"))
    atr = _fnum(row.get("ATR14"))
    atr_pct = atr / close * 100 if close > 0 and atr > 0 else 1.0
    roc20 = _fnum(row.get("ROC20"))
    macd_hist = _fnum(row.get("MACD_HIST"))
    rsi = _fnum(row.get("RSI14"), 50)

    impulse = roc20 / max(atr_pct * 2.5, 0.5)
    score = _clip(impulse * 6, -8, 8)

    if atr > 0:
        score += _clip((macd_hist / atr) * 120, -4, 4)

    if 55 <= rsi <= 68:
        score += 4
    elif 45 <= rsi < 55:
        score += 1.5
    elif rsi >= 75:
        score -= 2.5
    elif rsi <= 35:
        score -= 4

    if idx >= 3:
        score += 2 if close >= _fnum(df.iloc[idx - 3].get("Close"), close) else -2

    return _clip(score, -20, 20)


def score_structure(df: pd.DataFrame, idx: int) -> float:
    if idx < 8:
        return 0.0
    row = df.iloc[idx]
    win = df.iloc[max(0, idx - 20): idx + 1]
    score = 0.0

    first_high = _fnum(win.iloc[0].get("High"))
    mid_high = _fnum(win.iloc[len(win) // 2].get("High"), first_high)
    last_high = _fnum(win.iloc[-1].get("High"), mid_high)
    first_low = _fnum(win.iloc[0].get("Low"))
    mid_low = _fnum(win.iloc[len(win) // 2].get("Low"), first_low)
    last_low = _fnum(win.iloc[-1].get("Low"), mid_low)

    if last_high > mid_high > first_high:
        score += 5
    elif last_high < mid_high < first_high:
        score -= 5

    if last_low > mid_low > first_low:
        score += 5
    elif last_low < mid_low < first_low:
        score -= 5

    cloud_text, cloud_dir = _cloud_status(row)
    score += cloud_dir * 4

    kijun = _fnum(row.get("ICH_KIJUN"), _fnum(row.get("EMA20"), 0))
    close = _fnum(row.get("Close"))
    score += 3 if close >= kijun else -3

    range_pos = _range_pos(close, _fnum(win["Low"].min()), _fnum(win["High"].max()))
    if range_pos >= 0.65:
        score += 3
    elif range_pos <= 0.35:
        score -= 3

    bearish_bars = ((win["Close"] < win["Open"]) & (win["ClosePos"] < 0.4)).tail(6).sum()
    score -= min(4, bearish_bars)

    return _clip(score, -20, 20)


def score_compression(df: pd.DataFrame, idx: int) -> float:
    row = df.iloc[idx]
    score = 0.0

    atr14 = _fnum(row.get("ATR14"))
    atr60 = _fnum(row.get("ATR60"), atr14)
    if atr14 > 0 and atr60 > 0:
        ratio = atr14 / atr60
        if ratio <= 0.85:
            score += 6
        elif ratio >= 1.25:
            score -= 4

    bb_width = _fnum(row.get("BB_width"), np.nan)
    bb_hist = df["BB_width"].iloc[max(0, idx - 60): idx + 1].dropna()
    if len(bb_hist) >= 10 and not np.isnan(bb_width):
        pct_rank = float((bb_hist <= bb_width).mean())
        if pct_rank <= 0.25:
            score += 5
        elif pct_rank >= 0.85:
            score -= 3

    close = _fnum(row.get("Close"))
    range_pos = _range_pos(close, _fnum(row.get("RangeLow")), _fnum(row.get("RangeHigh")))
    if 0.55 <= range_pos <= 0.88:
        score += 5
    elif range_pos > 0.96:
        score -= 4
    elif range_pos < 0.35:
        score -= 5

    ema20 = _fnum(row.get("EMA20"), close)
    if atr14 > 0:
        stretch = abs(close - ema20) / atr14
        if stretch <= 1.2:
            score += 4
        elif stretch >= 3.0:
            score -= 4

    return _clip(score, -20, 20)


def score_volume(df: pd.DataFrame, idx: int) -> float:
    row = df.iloc[idx]
    rvol = _fnum(row.get("RVOL"), 1.0)
    close = _fnum(row.get("Close"))
    open_price = _fnum(row.get("Open"), close)
    close_pos = _fnum(row.get("ClosePos"), 0.5)
    score = 0.0

    if rvol >= 1.8:
        score += 4
    elif rvol >= 1.2:
        score += 2
    elif rvol < 0.75:
        score -= 2

    if close >= open_price and close_pos >= 0.65:
        score += 3 if rvol >= 1.0 else 1.5
    elif close < open_price and close_pos <= 0.35 and rvol >= 1.2:
        score -= 4

    recent = df.iloc[max(0, idx - 4): idx + 1]
    up_vol = _fnum(recent.loc[recent["Close"] >= recent["Open"], "Volume"].sum())
    down_vol = _fnum(recent.loc[recent["Close"] < recent["Open"], "Volume"].sum())
    if up_vol > down_vol * 1.2:
        score += 3
    elif down_vol > up_vol * 1.2 and down_vol > 0:
        score -= 3

    return _clip(score, -10, 10)


def score_risk_penalty(df: pd.DataFrame, idx: int) -> float:
    row = df.iloc[idx]
    close = _fnum(row.get("Close"))
    ema20 = _fnum(row.get("EMA20"), close)
    ema60 = _fnum(row.get("EMA60"), close)
    atr = _fnum(row.get("ATR14"))
    rvol = _fnum(row.get("RVOL"), 1.0)
    penalty = 0.0

    if atr > 0:
        gap_atr = (close - ema20) / atr
        if gap_atr >= 3.5:
            penalty -= 14
        elif gap_atr >= 2.7:
            penalty -= 8
        elif gap_atr <= -3.0:
            penalty -= 10
        elif gap_atr <= -2.2:
            penalty -= 6

    recent = df.iloc[max(0, idx - 4): idx + 1]
    upper_wick_count = int((recent["UpperWickRatio"].fillna(0) > 0.45).sum())
    penalty -= min(8, upper_wick_count * 2)

    close_pos = _fnum(row.get("ClosePos"), 0.5)
    if rvol >= 1.8 and close_pos <= 0.3 and close < _fnum(row.get("Open"), close):
        penalty -= 6

    range_pos = _range_pos(close, _fnum(row.get("RangeLow")), _fnum(row.get("RangeHigh")))
    if range_pos >= 0.97 and close < _fnum(row.get("Open"), close):
        penalty -= 4

    adx = _fnum(row.get("ADX14"), 18)
    if adx < 16 and abs(close - ema20) <= max(atr * 0.5, close * 0.004) and abs(close - ema60) <= max(atr * 0.8, close * 0.006):
        penalty -= 4

    return _clip(penalty, -30, 0)


def calc_fis(df: pd.DataFrame) -> pd.DataFrame:
    """차트 첫인상 점수 계산"""
    records = []
    for idx in range(len(df)):
        trend = score_trend(df, idx)
        momentum = score_momentum(df, idx)
        structure = score_structure(df, idx)
        compression = score_compression(df, idx)
        volume = score_volume(df, idx)
        risk = score_risk_penalty(df, idx)

        raw = (1.15 * trend) + momentum + structure + (0.85 * compression) + (0.75 * volume) + risk
        fis = _clip(raw * 1.05, -100, 100)

        records.append({
            "TrendScore": trend,
            "MomentumScore": momentum,
            "StructureScore": structure,
            "CompressionScore": compression,
            "VolumeScore": volume,
            "RiskPenalty": risk,
            "FIS": fis,
        })

    result = pd.DataFrame(records, index=df.index)
    return pd.concat([df, result], axis=1)


def calc_entry_score(df_fis: pd.DataFrame) -> dict:
    """현재 봉 기준 진입 타이밍 점수 계산 (0~100)."""
    row = df_fis.iloc[-1]
    fis = _fnum(row.get("FIS"))
    trend = _fnum(row.get("TrendScore"))
    momentum = _fnum(row.get("MomentumScore"))
    structure = _fnum(row.get("StructureScore"))
    compression = _fnum(row.get("CompressionScore"))
    volume_score = _fnum(row.get("VolumeScore"))
    risk = _fnum(row.get("RiskPenalty"))
    close = _fnum(row.get("Close"))
    open_price = _fnum(row.get("Open"), close)
    ema10 = _fnum(row.get("EMA10"), close)
    ema20 = _fnum(row.get("EMA20"), close)
    ema60 = _fnum(row.get("EMA60"), close)
    atr = _fnum(row.get("ATR14"))
    adx = _fnum(row.get("ADX14"), 18)
    rsi = _fnum(row.get("RSI14"), 50)
    rvol = _fnum(row.get("RVOL"), 1.0)
    bb_up = _fnum(row.get("BB_UP"), close)
    bb_dn = _fnum(row.get("BB_DN"), close)
    kijun = _fnum(row.get("ICH_KIJUN"), ema20)
    range_low = _fnum(row.get("RangeLow"))
    range_high = _fnum(row.get("RangeHigh"))
    close_pos = _fnum(row.get("ClosePos"), 0.5)
    roc20 = _fnum(row.get("ROC20"))

    gap_atr = (close - ema20) / atr if atr > 0 else 0.0
    gap_pct = (close - ema20) / ema20 * 100 if ema20 > 0 else 0.0
    lookback = df_fis.iloc[-8:] if len(df_fis) >= 8 else df_fis
    recent_high = _fnum(lookback["High"].max(), close)
    recent_low = _fnum(lookback["Low"].min(), close)
    pullback_pct = (recent_high - close) / recent_high * 100 if recent_high > 0 else 0.0
    bounce_pct = (close - recent_low) / recent_low * 100 if recent_low > 0 else 0.0
    range_pos = _range_pos(close, range_low, range_high)
    bb_pos = _range_pos(close, bb_dn, bb_up)
    hist_now = _fnum(row.get("MACD_HIST"))
    hist_prev = _fnum(df_fis.iloc[-2].get("MACD_HIST")) if len(df_fis) >= 2 else hist_now
    hist_prev2 = _fnum(df_fis.iloc[-3].get("MACD_HIST")) if len(df_fis) >= 3 else hist_prev
    hist_rising = hist_now >= hist_prev >= hist_prev2
    hist_falling = hist_now < hist_prev < hist_prev2

    cloud_top = max(_fnum(row.get("ICH_SENKOU_A"), np.nan), _fnum(row.get("ICH_SENKOU_B"), np.nan))
    cloud_ok = not np.isnan(cloud_top) and close >= cloud_top

    context = 0.0
    if fis >= 65:
        context += 16
    elif fis >= 45:
        context += 12
    elif fis >= 25:
        context += 8
    elif fis < 0:
        context -= 6
    if trend >= 14:
        context += 8
    elif trend >= 7:
        context += 4
    elif trend < 0:
        context -= 5
    if structure >= 8:
        context += 5
    elif structure < 0:
        context -= 4
    if adx >= 22:
        context += 4
    elif adx < 15:
        context -= 2
    if cloud_ok:
        context += 4
    if risk >= -6:
        context += 4
    elif risk <= -15:
        context -= 6
    context = _clip(context, 0, 30)

    pullback_setup = 0.0
    if -0.4 <= gap_atr <= 1.0:
        pullback_setup += 10
    elif 1.0 < gap_atr <= 1.8:
        pullback_setup += 6
    elif gap_atr > 2.8 or gap_atr < -1.2:
        pullback_setup -= 6
    if 4 <= pullback_pct <= 12:
        pullback_setup += 9
    elif 2 <= pullback_pct < 4:
        pullback_setup += 5
    elif pullback_pct > 16:
        pullback_setup -= 5
    if 43 <= rsi <= 58:
        pullback_setup += 7
    elif 38 <= rsi < 43:
        pullback_setup += 4
    elif rsi > 72:
        pullback_setup -= 4
    if rvol <= 1.05:
        pullback_setup += 4
    pullback_setup = _clip(pullback_setup, 0, 30)

    breakout_setup = 0.0
    if compression >= 8:
        breakout_setup += 8
    elif compression >= 4:
        breakout_setup += 4
    if 0.78 <= range_pos <= 0.96:
        breakout_setup += 8
    elif range_pos > 0.97:
        breakout_setup -= 4
    if rvol >= 1.4:
        breakout_setup += 7
    elif rvol >= 1.1:
        breakout_setup += 3
    if close_pos >= 0.72 and close >= open_price:
        breakout_setup += 4
    if hist_rising:
        breakout_setup += 5
    breakout_setup = _clip(breakout_setup, 0, 30)

    continuation_setup = 0.0
    if close >= ema10 >= ema20 >= ema60:
        continuation_setup += 9
    elif close >= ema10 >= ema20:
        continuation_setup += 5
    if momentum >= 8:
        continuation_setup += 7
    elif momentum >= 3:
        continuation_setup += 4
    if roc20 >= 8:
        continuation_setup += 5
    elif roc20 >= 4:
        continuation_setup += 3
    if hist_rising:
        continuation_setup += 4
    if rvol >= 1.2 and close_pos >= 0.65:
        continuation_setup += 5
    continuation_setup = _clip(continuation_setup, 0, 30)

    reversal_setup = 0.0
    if rsi <= 35:
        reversal_setup += 7
    elif rsi <= 42:
        reversal_setup += 4
    if bounce_pct >= 4:
        reversal_setup += 6
    elif bounce_pct >= 2:
        reversal_setup += 3
    if close >= ema10:
        reversal_setup += 5
    if hist_rising and hist_now > 0:
        reversal_setup += 5
    elif hist_rising:
        reversal_setup += 3
    if close_pos >= 0.65 and rvol >= 1.1:
        reversal_setup += 4
    reversal_setup = _clip(reversal_setup, 0, 24)

    setup_scores = {
        "추세 눌림": pullback_setup,
        "압축 돌파": breakout_setup,
        "모멘텀 지속": continuation_setup,
        "반전 초기": reversal_setup,
    }
    _sorted_setups = sorted(setup_scores.items(), key=lambda x: x[1], reverse=True)
    setup_name  = _sorted_setups[0][0]
    _primary    = _sorted_setups[0][1]
    _secondary  = _sorted_setups[1][1]
    # 2위 시나리오가 강할수록 가산점 (동시 다중 조건 정렬 보상)
    if _secondary >= 20:
        _consensus = (_secondary - 10) * 0.30
    elif _secondary >= 14:
        _consensus = (_secondary - 10) * 0.12
    else:
        _consensus = 0.0
    setup_quality = _clip(_primary + _consensus, 0, 30)
    # 2위 이름 (점수 18 이상일 때만 표시용으로 보존)
    setup_name2 = _sorted_setups[1][0] if _secondary >= 18 else ""

    trigger = 0.0
    if close >= ema10:
        trigger += 5
    if close >= ema20:
        trigger += 4
    if close >= kijun:
        trigger += 4
    if close_pos >= 0.62:
        trigger += 4
    elif close_pos <= 0.35:
        trigger -= 4
    if hist_rising:
        trigger += 5
    elif hist_falling:
        trigger -= 3
    if rvol >= 1.4 and close >= open_price:
        trigger += 4
    elif rvol < 0.75 and setup_name != "추세 눌림":
        trigger -= 2
    trigger = _clip(trigger, -6, 24)

    space = 0.0
    if 0.55 <= range_pos <= 0.9:
        space += 9
    elif 0.9 < range_pos <= 0.96:
        space += 4
    elif range_pos > 0.97:
        space -= 6
    elif range_pos < 0.35:
        space -= 3
    if 0.35 <= bb_pos <= 0.82:
        space += 5
    elif bb_pos > 0.92:
        space -= 4
    if risk >= -4:
        space += 4
    elif risk <= -15:
        space -= 4
    space = _clip(space, -6, 18)

    risk_control = 0.0
    if risk >= -4:
        risk_control += 10
    elif risk >= -9:
        risk_control += 6
    elif risk >= -14:
        risk_control += 2
    else:
        risk_control -= 4
    if atr > 0 and abs(close - ema20) / atr <= 2.2:
        risk_control += 4
    if adx >= 18:
        risk_control += 3
    risk_control = _clip(risk_control, 0, 16)

    # 이론적 최대합 118 기준으로 정규화 → 100 = 완벽한 셋업, 평범한 강세 ≈ 80~90
    _raw = context + setup_quality + trigger + space + risk_control
    total = _clip(round(_raw / 1.18), 0, 100)
    if total >= 80:
        label = "최적 진입 구간"
    elif total >= 65:
        label = "양호한 진입 구간"
    elif total >= 50:
        label = "조건부 진입 가능"
    else:
        label = "진입 대기 구간"

    return {
        "score": total,
        "label": label,
        "setup_name": setup_name,
        "setup_name2": setup_name2,
        "setup_scores": {k: round(v, 1) for k, v in setup_scores.items()},
        "components": {
            "추세문맥": round(context, 1),
            "진입구조": round(setup_quality, 1),
            "확인신호": round(trigger, 1),
            "저항여유": round(space, 1),
            "리스크관리": round(risk_control, 1),
        },
        "metrics": {
            "ema20_gap_pct": round(gap_pct, 2),
            "ema20_gap_atr": round(gap_atr, 2),
            "pullback_pct": round(pullback_pct, 2),
            "bounce_pct": round(bounce_pct, 2),
            "range_pos": round(range_pos * 100, 1),
            "bb_pos": round(bb_pos * 100, 1),
            "rsi_reset": round(rsi, 1),
            "adx": round(adx, 1),
        },
    }


def make_judgment(df_fis: pd.DataFrame) -> dict:
    """최신 봉 기준 판단 dict 반환"""
    row = df_fis.iloc[-1]
    fis = _fnum(row.get("FIS"))
    trend = _fnum(row.get("TrendScore"))
    momentum = _fnum(row.get("MomentumScore"))
    structure = _fnum(row.get("StructureScore"))
    compression = _fnum(row.get("CompressionScore"))
    volume = _fnum(row.get("VolumeScore"))
    risk = _fnum(row.get("RiskPenalty"))
    rsi = _fnum(row.get("RSI14"), 50)
    rvol = _fnum(row.get("RVOL"), 1.0)
    close = _fnum(row.get("Close"))

    if fis >= 65:
        label, label_color = "강한 상승 우위", "#D32F2F"
    elif fis >= 30:
        label, label_color = "상승 우위", "#E57373"
    elif fis >= 5:
        label, label_color = "중립 이상", "#F9A825"
    elif fis >= -20:
        label, label_color = "중립 약세", "#64B5F6"
    elif fis >= -50:
        label, label_color = "하락 우위", "#1565C0"
    else:
        label, label_color = "강한 하락 우위", "#0D47A1"

    contributors = {
        "추세": trend,
        "모멘텀": momentum,
        "구조": structure,
        "압축/위치": compression,
        "거래참여": volume,
        "위험": risk,
    }
    pos_name = max(contributors, key=contributors.get)
    neg_name = min(contributors, key=contributors.get)

    lead_clues = []
    if trend >= 14:
        lead_clues.append("이평 정렬과 추세 기울기가 견조하다")
    elif trend <= -8:
        lead_clues.append("이평 구조가 하방 쪽으로 틀어져 있다")

    if momentum >= 8:
        lead_clues.append("모멘텀 가속이 붙어 탄력이 살아 있다")
    elif momentum <= -6:
        lead_clues.append("모멘텀 둔화가 뚜렷해 추격은 불리하다")

    if structure >= 8:
        lead_clues.append("고점/저점 구조가 우상향으로 유지된다")
    elif structure <= -6:
        lead_clues.append("고점/저점 구조가 무너져 반등 신뢰가 낮다")

    if compression >= 8:
        lead_clues.append("압축 이후 확장 가능성이 열려 있다")
    elif compression <= -6:
        lead_clues.append("위치상 저항 부담이 커 상단 여유가 좁다")

    if volume >= 4:
        lead_clues.append("거래 참여가 붙어 신호 신뢰도가 보강된다")
    elif volume <= -3:
        lead_clues.append("거래 참여가 약해 신호 신뢰가 떨어진다")

    if not lead_clues:
        if fis >= 20:
            lead_clues.append("방향성은 우상향이나 확신 강도는 중간 수준이다")
        elif fis <= -20:
            lead_clues.append("방향성은 하방 우세이며 복원 신호가 부족하다")
        else:
            lead_clues.append("방향성 우위가 약해 추가 확인이 필요하다")

    lead_text = " · ".join(lead_clues[:2])

    risk_clues = []
    if risk <= -15:
        risk_clues.append("단기 과열/매물 부담이 커 리스크 관리가 우선이다")
    elif risk <= -8:
        risk_clues.append("리스크 감점이 누적되어 진입 크기 조절이 필요하다")
    elif risk >= -3:
        risk_clues.append("위험 감점이 낮아 관리 가능한 구간이다")

    if rsi >= 72:
        risk_clues.append(f"RSI {rsi:.1f}로 과열권이라 눌림 확인 후 접근이 유리하다")
    elif rsi <= 34:
        risk_clues.append(f"RSI {rsi:.1f} 저점권으로 반등 신호 확인이 핵심이다")

    if rvol >= 1.8:
        risk_clues.append("거래량 급증 구간이라 방향 확인 봉의 중요도가 높다")
    elif rvol < 0.8:
        risk_clues.append("거래량이 약해 돌파 신호의 지속성 검증이 필요하다")

    if fis >= 45:
        stance = "보유는 추세선 이탈 전까지 우위가 유지되며 신규 진입은 눌림/재돌파 확인이 유리하다"
    elif fis >= 10:
        stance = "보유는 중립 관리가 적절하고 신규 진입은 타이밍 점수와 저항 여유를 함께 확인해야 한다"
    elif fis >= -20:
        stance = "보유는 방어 비중을 높이고 신규 진입은 추세 복원 신호가 확인될 때까지 대기하는 편이 낫다"
    else:
        stance = "보유는 손절 기준 중심 방어가 우선이며 신규 진입은 공격적으로 보기 어렵다"

    sl1 = f"{lead_text}. 핵심 강점은 {pos_name}, 취약 지점은 {neg_name}이며 FIS는 {fis:.1f}이다."
    sl2 = f"{stance}. {risk_clues[0] if risk_clues else '진입 전 손익비와 손절 기준을 먼저 고정하는 것이 좋다.'} (RSI {rsi:.1f}, RVOL {rvol:.2f}x)"

    extra_parts = [f"가장 강한 강점은 {pos_name}이고, 가장 약한 부분은 {neg_name}이다."]
    if compression >= 8 and risk > -8:
        extra_parts.append("과열보다 재정비에 가까운 상태라 돌파 재개 가능성을 볼 수 있다.")
    if risk <= -15:
        extra_parts.append("단기 과열이나 매물 부담이 크므로 추격 매수는 불리하다.")
    if rvol >= 1.8:
        extra_parts.append("거래량이 늘어 방향 확인의 신뢰도는 다소 높아졌다.")
    extra = " ".join(extra_parts)

    ichimoku_status, _ = _cloud_status(row)
    if rsi >= 70:
        rsi_status = f"과매수 ({rsi:.1f})"
    elif rsi <= 30:
        rsi_status = f"과매도 ({rsi:.1f})"
    else:
        rsi_status = f"중립 ({rsi:.1f})"

    return {
        "fis": fis,
        "label": label,
        "label_color": label_color,
        "summary_l1": sl1,
        "summary_l2": sl2,
        "extra": extra,
        "ichimoku_status": ichimoku_status,
        "rsi_status": rsi_status,
        "scores": {
            "추세": trend,
            "모멘텀": momentum,
            "구조": structure,
            "압축": compression,
            "거래량": volume,
            "위험감점": risk,
        },
        "price": close,
    }
