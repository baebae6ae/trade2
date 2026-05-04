"""engine/fis.py — FIS(First Impression Score) 계산 + 한문장 판단"""

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────
# 레이어 1 — 방향 인상 (±30)
# 추세가 위인가 아래인가
# ─────────────────────────────────────────────────────────

def score_trend(row) -> float:
    """
    Close vs EMA20  : ±10
    Close vs EMA60  : ±10
    EMA20 vs EMA60  : ±5
    EMA60 vs EMA120 : ±5
    합계 최대 ±30
    """
    score = 0.0
    c = float(row["Close"])
    if c > row["EMA20"]:          score += 10
    else:                         score -= 10
    if c > row["EMA60"]:          score += 10
    else:                         score -= 10
    if row["EMA20"] > row["EMA60"]:  score += 5
    else:                            score -= 5
    if row["EMA60"] > row["EMA120"]: score += 5
    else:                            score -= 5
    return score


# ─────────────────────────────────────────────────────────
# 레이어 2 — 힘 인상 (±20)
# 강한가 약한가 — 10봉 수익률 ÷ ATR 정규화
# ─────────────────────────────────────────────────────────

def score_momentum(df: pd.DataFrame, idx: int) -> float:
    """
    최근 10봉 수익률을 ATR 기준으로 정규화
    정규화값 × 40 → clip(±20)
    """
    if idx < 10:
        return 0.0
    row  = df.iloc[idx]
    past = float(df.iloc[idx - 10]["Close"])
    ret10 = (float(row["Close"]) - past) / past if past != 0 else 0.0
    atr   = float(row["ATR14"])
    c     = float(row["Close"])
    norm  = ret10 * c / atr if atr != 0 else 0.0
    return float(np.clip(norm * 40, -20, 20))


# ─────────────────────────────────────────────────────────
# 레이어 3 — 구조 인상 (±20)
# 고저점 계단 + MA 배열 + 역방향 캔들
# ─────────────────────────────────────────────────────────

def score_structure(df: pd.DataFrame, idx: int) -> float:
    """
    고점 계단식 상승/하락 : ±6
    저점 계단식 상승/하락 : ±6
    최근 10봉 큰 음봉 수  : -2/개 (최대 -8)
    EMA 정배열/역배열     : ±8
    합계 clip(±20)
    """
    if idx < 20:
        return 0.0
    win    = df.iloc[idx - 20: idx + 1]
    highs  = win["High"].values
    lows   = win["Low"].values
    closes = win["Close"].values
    opens  = win["Open"].values
    atr    = float(df.iloc[idx]["ATR14"])
    score  = 0.0

    # 고점 구조
    if highs[-1] > highs[-11] > highs[0]:    score += 6
    elif highs[-1] < highs[-11] < highs[0]:  score -= 6

    # 저점 구조
    if lows[-1] > lows[-11] > lows[0]:       score += 6
    elif lows[-1] < lows[-11] < lows[0]:     score -= 6

    # 최근 10봉 큰 역방향(음봉) 캔들 감점
    big_bear = sum(
        1 for i in range(-10, 0)
        if (closes[i] < opens[i]) and abs(closes[i] - opens[i]) > atr * 0.8
    )
    score -= min(8, big_bear * 2)

    # EMA 배열
    last = df.iloc[idx]
    if last["EMA10"] > last["EMA20"] > last["EMA60"]:    score += 8
    elif last["EMA10"] < last["EMA20"] < last["EMA60"]:  score -= 8

    return float(np.clip(score, -20, 20))


# ─────────────────────────────────────────────────────────
# 레이어 4 — 압축/위치 인상 (±20)
# 공간이 있는가, 돌파 직전인가
# ─────────────────────────────────────────────────────────

def score_compression(df: pd.DataFrame, idx: int) -> float:
    """
    ATR14 < ATR60 × 0.75 (변동성 수축)   : +8
    ATR14 > ATR60 × 1.3  (과도 확장)      : -4
    BB폭  < 60봉 하위25%                  : +6
    52주 고점 여유 > 20%                  : +6
    52주 고점 여유 < 5%  (저항 근접)      : -6
    합계 clip(±20)
    """
    if idx < 60:
        return 0.0
    row   = df.iloc[idx]
    score = 0.0

    # 변동성 수축
    if row["ATR14"] < row["ATR60"] * 0.75:
        score += 8
    elif row["ATR14"] > row["ATR60"] * 1.3:
        score -= 4

    # 볼린저 폭 수축
    bb_hist = df["BB_width"].iloc[max(0, idx - 60): idx + 1]
    if row["BB_width"] < bb_hist.quantile(0.25):
        score += 6

    # 52주 고점 공간
    h52 = float(row["High52"])
    c   = float(row["Close"])
    if h52 > 0:
        room = (h52 - c) / h52
        if room > 0.20:    score += 6
        elif room < 0.05:  score -= 6

    return float(np.clip(score, -20, 20))


# ─────────────────────────────────────────────────────────
# 레이어 5 — 거래량 인상 (±10)
# ─────────────────────────────────────────────────────────

def score_volume(row) -> float:
    """
    RVOL > 2.0  : +10
    RVOL > 1.5  : +6
    RVOL > 1.0  : +2
    RVOL > 0.7  : -2
    else        : -6
    """
    rvol = float(row.get("RVOL", 1.0))
    if np.isnan(rvol):  return 0.0
    if rvol > 2.0:      return 10.0
    elif rvol > 1.5:    return 6.0
    elif rvol > 1.0:    return 2.0
    elif rvol > 0.7:    return -2.0
    return -6.0


# ─────────────────────────────────────────────────────────
# 위험 감점 (최대 -30)
# ─────────────────────────────────────────────────────────

def score_risk_penalty(df: pd.DataFrame, idx: int) -> float:
    """
    EMA20 이격 > 3 ATR   : -15
    EMA20 이격 > 2 ATR   : -8
    (음방향 동일 적용)
    최근 5봉 윗꼬리 과다  : -2/개 (최대 -10)
    RVOL>2 + 종가하위30% : -8 (분산 매도 징후)
    합계 최대 -30
    """
    if idx < 5:
        return 0.0
    row     = df.iloc[idx]
    penalty = 0.0
    c       = float(row["Close"])
    atr     = float(row["ATR14"])
    ema20   = float(row["EMA20"])

    # 과열/과매도 이격
    if atr > 0:
        gap = (c - ema20) / atr
        if   gap >  3.0:  penalty -= 15
        elif gap >  2.0:  penalty -= 8
        elif gap < -3.0:  penalty -= 15
        elif gap < -2.0:  penalty -= 8

    # 윗꼬리 과다 (최근 5봉)
    upper_tails = 0
    for _, r in df.iloc[max(0, idx - 5): idx + 1].iterrows():
        body = abs(float(r["Close"]) - float(r["Open"]))
        tail = float(r["High"]) - max(float(r["Close"]), float(r["Open"]))
        if body > 0 and tail > body * 0.5:
            upper_tails += 1
    penalty -= min(10, upper_tails * 2)

    # 거래량 폭증 후 종가 약함 (분산 매도)
    if float(row["RVOL"]) > 2.0:
        day_range = float(row["High"]) - float(row["Low"])
        if day_range > 0:
            close_pos = (float(row["Close"]) - float(row["Low"])) / day_range
            if close_pos < 0.3:
                penalty -= 8

    return float(np.clip(penalty, -30, 0))


# ─────────────────────────────────────────────────────────
# FIS 종합 계산
# ─────────────────────────────────────────────────────────

def calc_fis(df: pd.DataFrame) -> pd.DataFrame:
    """
    FIS = clip(1.2 × (Trend + Momentum + Structure + Compression + Volume + RiskPenalty), -100, 100)

    각 레이어 점수는 가중 합산이 아닌 직접 합산.
    최대 raw = 30+20+20+20+10 = 100  → FIS max ≈ 100
    최소 raw ≈ -30-20-20-20-10-30   → FIS min ≈ -100
    """
    records = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        t   = score_trend(row)
        m   = score_momentum(df, idx)
        s   = score_structure(df, idx)
        cb  = score_compression(df, idx)
        vl  = score_volume(row)
        rp  = score_risk_penalty(df, idx)

        # 직접 합산 (가중치 없음) — 각 레이어 점수 범위가 이미 보정돼 있음
        raw = t + m + s + cb + vl + rp
        fis = float(np.clip(raw * 1.2, -100, 100))

        records.append({
            "TrendScore":       t,
            "MomentumScore":    m,
            "StructureScore":   s,
            "CompressionScore": cb,
            "VolumeScore":      vl,
            "RiskPenalty":      rp,
            "FIS":              fis,
        })

    result = pd.DataFrame(records, index=df.index)
    return pd.concat([df, result], axis=1)


# ─────────────────────────────────────────────────────────
# 한문장 판단 생성
# ─────────────────────────────────────────────────────────

def make_judgment(df_fis: pd.DataFrame) -> dict:
    """최신 봉 기준으로 판단 dict 반환"""
    row  = df_fis.iloc[-1]
    fis  = float(row["FIS"])
    t    = float(row["TrendScore"])
    m    = float(row["MomentumScore"])
    s    = float(row["StructureScore"])
    cb   = float(row["CompressionScore"])
    rp   = float(row["RiskPenalty"])
    rvol = float(row["RVOL"]) if not pd.isna(row["RVOL"]) else 1.0

    # ── 첫인상 레이블 ──────────────────────────
    if fis >= 70:
        label, label_color = "강한 상승형",   "#D32F2F"
    elif fis >= 40:
        label, label_color = "우호적 추세형", "#E57373"
    elif fis >= 10:
        label, label_color = "중립 관망형",   "#F9A825"
    elif fis >= -20:
        label, label_color = "약세 주의형",   "#64B5F6"
    elif fis >= -50:
        label, label_color = "하락 압력형",   "#1565C0"
    else:
        label, label_color = "강한 하락형",   "#0D47A1"

    # ── 요약 2줄 (FIS 구간별) ─────────────────
    if fis >= 40:
        sl1 = "추세는 살아 있고 눌림 확인이 중요한 구간이다. 신규 진입은 눌림이 지지로 확인될 때만 의미가 있다."
        sl2 = "보유자는 추세 훼손 전까지 관찰 유지가 가능하다. 중요한 기준선 근처에서 눌림이 잡히면 위치는 나쁘지 않다."
    elif fis >= 10:
        sl1 = "나쁘지 않지만 한두 번 더 확인이 필요한 구간이다. 신규 진입은 서두르기보다 조건 확인이 먼저다."
        sl2 = "보유자는 추세 훼손 전까지 관찰 유지가 가능하다. 중요한 기준선 근처에서 눌림이 잡히면 위치는 나쁘지 않다."
    elif fis >= -20:
        sl1 = "첫인상만 보고 들어가기에는 근거가 부족한 구간이다. 신규 진입은 보류하고 다음 확인을 기다리는 편이 낫다."
        sl2 = "보유자는 큰 방향이 다시 정리되는지 확인하는 편이 낫다. 주요 기준선이 흔들리면 방어 관점으로 바꿔야 한다."
    elif fis >= -50:
        sl1 = "하락 압력이 강한 구간이다. 신규 진입은 부담이 있으므로 반등 확인 후 재판단이 필요하다."
        sl2 = "보유자는 추가 하락 시 손절 기준을 재점검해야 한다. 다음 봉에서 반전 신호가 없으면 방어 관점을 유지한다."
    else:
        sl1 = "추세가 완전히 꺾인 구간이다. 매수 접근은 매우 위험하다."
        sl2 = "보유자는 손절 기준을 재점검하고 방어적 관점을 유지해야 한다."

    # ── 세부 추가 코멘트 ──────────────────────
    extra_parts = []
    if cb >= 10 and rp > -5:
        extra_parts.append("변동성 수축 후 돌파 가능성을 주시할 구간이다.")
    elif rp <= -15:
        extra_parts.append("단기 과열 또는 매물 부담이 크므로 추격보다 조정 대기가 낫다.")
    if rvol > 2.0:
        extra_parts.append("거래량이 크게 증가해 방향 확인이 필요하다.")
    extra = " ".join(extra_parts)

    # ── 일목균형표 구름 위치 ──────────────────
    cloud_a = float(row.get("ICH_SENKOU_A", 0) or 0)
    cloud_b = float(row.get("ICH_SENKOU_B", 0) or 0)
    c_price = float(row["Close"])
    cloud_top = max(cloud_a, cloud_b)
    cloud_bot = min(cloud_a, cloud_b)
    if c_price > cloud_top:
        ichimoku_status = "구름 위 — 매수 우세"
    elif c_price < cloud_bot:
        ichimoku_status = "구름 아래 — 매도 우세"
    else:
        ichimoku_status = "구름 내부 — 중립"

    # ── RSI 상태 ─────────────────────────────
    rsi = float(row.get("RSI14", 50) or 50)
    if rsi >= 70:
        rsi_status = f"과매수 ({rsi:.1f})"
    elif rsi <= 30:
        rsi_status = f"과매도 ({rsi:.1f})"
    else:
        rsi_status = f"중립 ({rsi:.1f})"

    return {
        "fis":             fis,
        "label":           label,
        "label_color":     label_color,
        "summary_l1":      sl1,
        "summary_l2":      sl2,
        "extra":           extra,
        "ichimoku_status": ichimoku_status,
        "rsi_status":      rsi_status,
        "scores": {
            "추세":    t,
            "모멘텀":  m,
            "구조":    s,
            "압축":    cb,
            "거래량":  float(row["VolumeScore"]),
            "위험감점": rp,
        },
    }
