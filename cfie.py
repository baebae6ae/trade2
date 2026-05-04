"""
CFIE v3.7 — Chart First Impression Engine
차트 첫인상 점수(FIS) 계산 + 한 문장 판단 + 캔들차트 시각화

사용법:
    python cfie.py                      # 종목 선택 화면
    python cfie.py --ticker 005380.KS   # 현대차 직접 실행
    python cfie.py --ticker INTC        # 인텔 직접 실행
"""

import argparse
import warnings
import sys
import math
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.family"] = ["Malgun Gothic", "AppleGothic", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

# ──────────────────────────────────────────────
# 1. 데이터 수집
# ──────────────────────────────────────────────

def fetch(ticker: str, period: str = "1y") -> pd.DataFrame:
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"데이터 없음: {ticker}")
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    return df

# ──────────────────────────────────────────────
# 2. 보조 지표 계산
# ──────────────────────────────────────────────

def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"].squeeze()
    h = df["High"].squeeze()
    lo = df["Low"].squeeze()
    v = df["Volume"].squeeze()

    df = df.copy()
    df["EMA10"]  = c.ewm(span=10,  adjust=False).mean()
    df["EMA20"]  = c.ewm(span=20,  adjust=False).mean()
    df["EMA60"]  = c.ewm(span=60,  adjust=False).mean()
    df["EMA120"] = c.ewm(span=120, adjust=False).mean()

    # ATR
    tr = pd.concat([
        h - lo,
        (h - c.shift(1)).abs(),
        (lo - c.shift(1)).abs()
    ], axis=1).max(axis=1)
    df["ATR14"] = tr.ewm(span=14, adjust=False).mean()
    df["ATR60"] = tr.ewm(span=60, adjust=False).mean()

    # 볼린저밴드 폭
    std20 = c.rolling(20).std()
    df["BB_width"] = (std20 * 4) / df["EMA20"]

    # 거래량 이평
    df["Vol20"]  = v.rolling(20).mean()
    df["Vol60"]  = v.rolling(60).mean()
    df["RVOL"]   = v / df["Vol20"].replace(0, np.nan)

    # 52주 고/저
    df["High52"] = h.rolling(252).max()
    df["Low52"]  = lo.rolling(252).min()

    return df.dropna()


# ──────────────────────────────────────────────
# 3. FIS 점수 계산 (5레이어)
# ──────────────────────────────────────────────

def score_trend(row) -> float:
    """방향 인상: 위인가 아래인가 (최대 ±30)"""
    score = 0.0
    c = row["Close"]
    if c > row["EMA20"]:  score += 10
    else:                 score -= 10
    if c > row["EMA60"]:  score += 10
    else:                 score -= 10
    if row["EMA20"] > row["EMA60"]: score += 5
    else:                           score -= 5
    if row["EMA60"] > row["EMA120"]: score += 5
    else:                            score -= 5
    return score


def score_momentum(df: pd.DataFrame, idx: int) -> float:
    """힘 인상: 강한가 약한가 (최대 ±20)"""
    if idx < 10:
        return 0.0
    row = df.iloc[idx]
    past = df.iloc[idx - 10]["Close"]
    ret10 = (row["Close"] - past) / past if past != 0 else 0
    atr = row["ATR14"]
    c = row["Close"]
    norm = ret10 * c / atr if atr != 0 else 0  # ATR 정규화 수익률
    # 클리핑
    score = max(-20, min(20, norm * 40))
    return score


def score_structure(df: pd.DataFrame, idx: int) -> float:
    """질서 인상: 깨끗한가 지저분한가 (최대 ±20)"""
    if idx < 20:
        return 0.0
    win = df.iloc[idx - 20: idx + 1]
    score = 0.0
    highs = win["High"].values
    lows  = win["Low"].values
    closes = win["Close"].values
    opens  = win["Open"].values

    # 고점이 계단식 상승?
    if highs[-1] > highs[-11] > highs[0]:  score += 6
    elif highs[-1] < highs[-11] < highs[0]: score -= 6

    # 저점이 계단식 상승?
    if lows[-1] > lows[-11] > lows[0]:   score += 6
    elif lows[-1] < lows[-11] < lows[0]: score -= 6

    # 큰 역방향 캔들 (음봉 5개 이상이면 감점)
    big_bear = sum(1 for i in range(-10, 0)
                   if (closes[i] < opens[i]) and
                   abs(closes[i] - opens[i]) > df.iloc[idx]["ATR14"] * 0.8)
    score -= min(8, big_bear * 2)

    # EMA 배열 정돈 (단기 > 중기 > 장기)
    last = df.iloc[idx]
    if last["EMA10"] > last["EMA20"] > last["EMA60"]: score += 8
    elif last["EMA10"] < last["EMA20"] < last["EMA60"]: score -= 8

    return max(-20, min(20, score))


def score_compression(df: pd.DataFrame, idx: int) -> float:
    """위치/압축 인상: 공간이 있는가, 돌파 직전인가 (최대 ±20)"""
    if idx < 60:
        return 0.0
    row = df.iloc[idx]
    score = 0.0

    # 변동성 수축
    if row["ATR14"] < row["ATR60"] * 0.75:
        score += 8  # 압축 상태
    elif row["ATR14"] > row["ATR60"] * 1.3:
        score -= 4  # 과도한 확장

    # BB 폭 수축
    bb_hist = df["BB_width"].iloc[max(0, idx-60):idx+1]
    if row["BB_width"] < bb_hist.quantile(0.25):
        score += 6

    # 52주 고점까지 거리 — 공간 많을수록 가산
    h52 = row["High52"]
    c = row["Close"]
    if h52 > 0:
        room = (h52 - c) / h52
        if room > 0.20:   score += 6   # 공간 충분
        elif room < 0.05: score -= 6   # 52주 고점 근접(저항)

    return max(-20, min(20, score))


def score_volume(row) -> float:
    """거래량 인상 (최대 ±10)"""
    rvol = row.get("RVOL", 1.0)
    if rvol > 2.0:   return 10
    elif rvol > 1.5: return 6
    elif rvol > 1.0: return 2
    elif rvol > 0.7: return -2
    else:            return -6


def score_risk_penalty(df: pd.DataFrame, idx: int) -> float:
    """위험 감점 (최대 -30)"""
    if idx < 5:
        return 0.0
    row = df.iloc[idx]
    penalty = 0.0
    c = row["Close"]
    atr = row["ATR14"]
    ema20 = row["EMA20"]

    # 과열: EMA20 대비 이격
    if atr > 0:
        gap = (c - ema20) / atr
        if gap > 3.0:   penalty -= 15
        elif gap > 2.0: penalty -= 8
        elif gap < -3.0: penalty -= 15
        elif gap < -2.0: penalty -= 8

    # 윗꼬리 과다
    recent = df.iloc[max(0, idx-5): idx+1]
    upper_tails = 0
    for _, r in recent.iterrows():
        body = abs(r["Close"] - r["Open"])
        tail = r["High"] - max(r["Close"], r["Open"])
        if body > 0 and tail > body * 0.5:
            upper_tails += 1
    penalty -= min(10, upper_tails * 2)

    # 거래량 폭증 후 종가 약함 (분산 매도 징후)
    if row["RVOL"] > 2.0:
        day_range = row["High"] - row["Low"]
        close_pos = (row["Close"] - row["Low"]) / day_range if day_range > 0 else 0.5
        if close_pos < 0.3:
            penalty -= 8

    return max(-30, penalty)


def calc_fis(df: pd.DataFrame) -> pd.DataFrame:
    """전체 행에 대해 FIS 점수 계산"""
    records = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        t  = score_trend(row)
        m  = score_momentum(df, idx)
        s  = score_structure(df, idx)
        cb = score_compression(df, idx)
        vl = score_volume(row)
        rp = score_risk_penalty(df, idx)

        raw = (0.28 * t + 0.20 * m + 0.17 * s +
               0.17 * cb + 0.10 * vl + rp)

        # 정규화: -100 ~ +100
        fis = max(-100, min(100, raw * 1.2))
        records.append({
            "TrendScore": t,
            "MomentumScore": m,
            "StructureScore": s,
            "CompressionScore": cb,
            "VolumeScore": vl,
            "RiskPenalty": rp,
            "FIS": fis
        })
    result = pd.DataFrame(records, index=df.index)
    return pd.concat([df, result], axis=1)


# ──────────────────────────────────────────────
# 4. 한 문장 판단 생성
# ──────────────────────────────────────────────

def one_sentence(df_fis: pd.DataFrame) -> dict:
    """최신 봉 기준 한 문장 판단 반환"""
    row = df_fis.iloc[-1]
    fis  = row["FIS"]
    t    = row["TrendScore"]
    m    = row["MomentumScore"]
    s    = row["StructureScore"]
    cb   = row["CompressionScore"]
    rp   = row["RiskPenalty"]
    rvol = row["RVOL"]

    # 첫인상 레이블
    if fis >= 70:
        label = "강한 상승형"
        label_color = "#D32F2F"
    elif fis >= 40:
        label = "우호적 추세형"
        label_color = "#E57373"
    elif fis >= 10:
        label = "중립 관망형"
        label_color = "#F9A825"
    elif fis >= -20:
        label = "약세 주의형"
        label_color = "#64B5F6"
    elif fis >= -50:
        label = "하락 압력형"
        label_color = "#1565C0"
    else:
        label = "강한 하락형"
        label_color = "#0D47A1"

    # 세부 문장 조합
    parts = []

    # 추세 판단
    if t >= 20:
        parts.append("추세는 살아 있고")
    elif t >= 0:
        parts.append("추세는 중립 구간이며")
    else:
        parts.append("추세가 무너진 상태로")

    # 힘 판단
    if m >= 10:
        parts.append("최근 상승 모멘텀이 강하다.")
    elif m >= 0:
        parts.append("모멘텀은 보통 수준이다.")
    else:
        parts.append("모멘텀이 약하거나 반전 중이다.")

    # 질서/구조
    if s >= 10:
        extra = "고저점 구조가 양호해 신규 진입 시 눌림 확인 후 접근이 유효하다."
    elif s >= -5:
        extra = "차트 구조는 무난하나 추가 확인이 필요하다."
    else:
        extra = "고저점 구조가 흔들려 신뢰도가 낮으므로 관망이 우선이다."

    # 압축/위험 추가
    if cb >= 10 and rp > -5:
        extra += " 변동성 수축 후 돌파 가능성을 주시할 구간이다."
    elif rp <= -15:
        extra += " 단기 과열 또는 매물 부담이 크므로 추격보다 조정 대기가 낫다."

    # 거래량 언급
    if rvol > 2.0:
        extra += " 거래량이 크게 증가해 방향 확인이 필요하다."

    sentence = " ".join(parts) + " " + extra

    # 요약(2줄)
    if fis >= 40:
        summary_l1 = "추세와 힘이 우호적이다. 신규 진입은 눌림이 지지로 확인될 때만 의미가 있다."
        summary_l2 = "보유자는 추세 훼손 전까지 관찰 유지가 가능하다. 중요한 기준선 근처에서 눌림이 잡히면 위치는 나쁘지 않다."
    elif fis >= 10:
        summary_l1 = "나쁘지 않지만 한두 번 더 확인이 필요한 구간이다. 신규 진입은 서두르기보다 조건 확인이 먼저다."
        summary_l2 = "보유자는 추세 훼손 전까지 관찰 유지가 가능하다. 중요한 기준선 근처에서 눌림이 잡히면 위치는 나쁘지 않다."
    elif fis >= -20:
        summary_l1 = "첫인상만 보고 들어가기에는 근거가 부족한 구간이다. 신규 진입은 보류하고 다음 확인을 기다리는 편이 낫다."
        summary_l2 = "보유자는 큰 방향이 다시 정리되는지 확인하는 편이 낫다. 주요 기준선이 흔들리면 방어 관점으로 바꿔야 한다."
    elif fis >= -50:
        summary_l1 = "강한 임펄스 구간이다. 신규 진입은 부담이 있으므로 돌파 추격보다 짧은 눌림이나 재가속 확인이 필요하다."
        summary_l2 = "보유자는 추세가 꺾이기 전까지 끌고 갈 수 있다. 다음 봉에서 힘이 유지되는지 확인하면 된다."
    else:
        summary_l1 = "추세가 완전히 꺾인 구간이다. 매수 접근은 매우 위험하다."
        summary_l2 = "보유자는 손절 기준을 재점검하고 방어적 관점을 유지해야 한다."

    return {
        "fis": fis,
        "label": label,
        "label_color": label_color,
        "sentence": sentence,
        "summary_l1": summary_l1,
        "summary_l2": summary_l2,
        "scores": {
            "추세": t,
            "모멘텀": m,
            "구조": s,
            "압축": cb,
            "거래량": row["VolumeScore"],
            "위험감점": rp
        }
    }


# ──────────────────────────────────────────────
# 5. 차트 시각화
# ──────────────────────────────────────────────

def plot_chart(ticker: str, df_fis: pd.DataFrame, judgment: dict, display_bars: int = 220):
    df_plot = df_fis.iloc[-display_bars:].copy()
    n = len(df_plot)
    dates = np.arange(n)

    fig = plt.figure(figsize=(16, 9), facecolor="#131722")
    gs = gridspec.GridSpec(3, 1, height_ratios=[5, 1, 1],
                           hspace=0.04, left=0.06, right=0.88,
                           top=0.95, bottom=0.06)

    ax_c  = fig.add_subplot(gs[0])   # 캔들
    ax_v  = fig.add_subplot(gs[1], sharex=ax_c)  # 거래량
    ax_f  = fig.add_subplot(gs[2], sharex=ax_c)  # FIS

    for ax in [ax_c, ax_v, ax_f]:
        ax.set_facecolor("#131722")
        ax.tick_params(colors="#B2B5BE", labelsize=8)
        for sp in ax.spines.values():
            sp.set_edgecolor("#2A2E39")

    # ── 캔들 ──
    for i, (idx, row) in enumerate(df_plot.iterrows()):
        o, h, lo, c = row["Open"], row["High"], row["Low"], row["Close"]
        color = "#E53935" if c >= o else "#1E88E5"
        ax_c.plot([i, i], [lo, h], color=color, lw=0.8, zorder=2)
        rect_y = min(o, c)
        rect_h = max(abs(c - o), 0.001 * c)
        rect = plt.Rectangle((i - 0.35, rect_y), 0.7, rect_h,
                              color=color, zorder=3)
        ax_c.add_patch(rect)

    # ── 이동평균 ──
    for col, color, lw, label in [
        ("EMA10",  "#F6C90E", 1.0, "EMA10"),
        ("EMA20",  "#FF6F00", 1.2, "EMA20"),
        ("EMA60",  "#7E57C2", 1.4, "EMA60"),
        ("EMA120", "#26A69A", 1.2, "EMA120"),
    ]:
        vals = df_plot[col].values
        ax_c.plot(dates, vals, color=color, lw=lw, label=label, zorder=4)

    ax_c.set_xlim(-1, n + 1)
    ax_c.yaxis.tick_right()
    ax_c.yaxis.set_label_position("right")
    ax_c.grid(axis="y", color="#2A2E39", lw=0.5)
    ax_c.legend(loc="upper left", fontsize=7,
                facecolor="#1E222D", edgecolor="#2A2E39",
                labelcolor="white", ncol=4)

    # ── 거래량 ──
    for i, (idx, row) in enumerate(df_plot.iterrows()):
        o, c, v = row["Open"], row["Close"], row["Volume"]
        color = "#E5393580" if c >= o else "#1E88E580"
        ax_v.bar(i, v, color=color, width=0.7, zorder=2)
    vol20 = df_plot["Vol20"].values
    ax_v.plot(dates, vol20, color="#B2B5BE", lw=0.8, zorder=3)
    ax_v.set_ylabel("Vol", color="#B2B5BE", fontsize=7)
    ax_v.yaxis.tick_right()
    ax_v.yaxis.set_ticklabels([])
    ax_v.grid(axis="y", color="#2A2E39", lw=0.4)

    # ── FIS 바 ──
    fis_vals = df_plot["FIS"].values
    for i, fv in enumerate(fis_vals):
        color = "#E53935" if fv >= 0 else "#1E88E5"
        ax_f.bar(i, fv, color=color, width=0.7, zorder=2)
    ax_f.axhline(0, color="#B2B5BE", lw=0.6)
    ax_f.axhline(40,  color="#E53935", lw=0.4, ls="--")
    ax_f.axhline(-40, color="#1E88E5", lw=0.4, ls="--")
    ax_f.set_ylim(-100, 100)
    ax_f.yaxis.tick_right()
    ax_f.set_ylabel("FIS", color="#B2B5BE", fontsize=7)
    ax_f.grid(axis="y", color="#2A2E39", lw=0.4)

    # X축 날짜 라벨
    step = max(1, n // 10)
    tick_pos  = list(range(0, n, step))
    tick_labs = [df_plot.index[i].strftime("%y/%m") for i in tick_pos]
    ax_f.set_xticks(tick_pos)
    ax_f.set_xticklabels(tick_labs, color="#B2B5BE", fontsize=8)
    plt.setp(ax_c.get_xticklabels(), visible=False)
    plt.setp(ax_v.get_xticklabels(), visible=False)

    # ── CFIE 판단 박스 (우측 상단 오버레이) ──
    fis     = judgment["fis"]
    label   = judgment["label"]
    lcolor  = judgment["label_color"]
    sl1     = judgment["summary_l1"]
    sl2     = judgment["summary_l2"]

    # 박스 좌표 (axes fraction)
    box_x, box_y = 0.42, 0.965
    box_w, box_h = 0.575, 0.135

    # 상단 헤더 바
    header_ax = fig.add_axes([box_x, box_y, box_w, 0.028])
    header_ax.set_facecolor("#1E222D")
    header_ax.set_xlim(0, 1); header_ax.set_ylim(0, 1)
    header_ax.axis("off")
    header_ax.text(0.02, 0.5, f"CFIE v3.7", va="center", ha="left",
                   color="#B2B5BE", fontsize=9, fontweight="bold",
                   transform=header_ax.transAxes)
    header_ax.text(0.5, 0.5, "한문장 판단", va="center", ha="center",
                   color="white", fontsize=10, fontweight="bold",
                   transform=header_ax.transAxes)
    # FIS 점수 표시
    fis_color = lcolor
    header_ax.text(0.98, 0.5, f"FIS {fis:+.0f}", va="center", ha="right",
                   color=fis_color, fontsize=9, fontweight="bold",
                   transform=header_ax.transAxes)

    # 본문 박스
    body_y = box_y - box_h
    body_ax = fig.add_axes([box_x, body_y, box_w, box_h])
    body_ax.set_facecolor("#1A1E2E")
    body_ax.set_xlim(0, 1); body_ax.set_ylim(0, 1)
    body_ax.axis("off")

    # 라벨 칩
    chip = FancyBboxPatch((0.01, 0.60), 0.13, 0.32,
                          boxstyle="round,pad=0.01",
                          facecolor=lcolor, edgecolor="none",
                          transform=body_ax.transAxes)
    body_ax.add_patch(chip)
    body_ax.text(0.075, 0.76, "요약", va="center", ha="center",
                 color="white", fontsize=9, fontweight="bold",
                 transform=body_ax.transAxes)

    # 요약 줄1
    body_ax.text(0.16, 0.82, sl1, va="center", ha="left",
                 color="#E0E3EB", fontsize=8.5,
                 transform=body_ax.transAxes,
                 wrap=True)
    # 요약 줄2
    body_ax.text(0.16, 0.58, sl2, va="center", ha="left",
                 color="#E0E3EB", fontsize=8.5,
                 transform=body_ax.transAxes,
                 wrap=True)

    # 구분선
    body_ax.plot([0.01, 0.99], [0.45, 0.45],
                 color="#2A2E39", lw=0.8,
                 transform=body_ax.transAxes, clip_on=False)

    # 세부 점수 바 (하단)
    scores = judgment["scores"]
    keys   = list(scores.keys())
    vals   = [scores[k] for k in keys]
    bar_colors = ["#E53935" if v >= 0 else "#1E88E5" for v in vals]

    bar_ax = fig.add_axes([box_x + 0.01, body_y + 0.005,
                           box_w - 0.02, box_h * 0.40])
    bar_ax.set_facecolor("#1A1E2E")
    bar_ax.barh(keys, vals, color=bar_colors, height=0.55)
    bar_ax.axvline(0, color="#B2B5BE", lw=0.6)
    bar_ax.set_xlim(-30, 30)
    bar_ax.set_xlim(-35, 35)
    bar_ax.tick_params(colors="#B2B5BE", labelsize=7.5)
    bar_ax.set_facecolor("#1A1E2E")
    for sp in bar_ax.spines.values():
        sp.set_visible(False)
    bar_ax.tick_params(left=True, bottom=False,
                       labelleft=True, labelbottom=False)
    bar_ax.yaxis.tick_left()

    # 첫인상 라벨 (캔들 차트 우측 상단 귀퉁이)
    ax_c.text(0.01, 0.97, f"첫인상: {label}",
              transform=ax_c.transAxes,
              va="top", ha="left",
              color=lcolor, fontsize=11, fontweight="bold",
              bbox=dict(facecolor="#131722", edgecolor="none",
                        alpha=0.7, pad=2))

    # 종목명 + 현재가
    last = df_fis.iloc[-1]
    close_val = float(last["Close"])
    ax_c.text(0.01, 0.90, f"{ticker}  {close_val:,.2f}",
              transform=ax_c.transAxes,
              va="top", ha="left",
              color="#B2B5BE", fontsize=10,
              bbox=dict(facecolor="#131722", edgecolor="none", alpha=0.6, pad=2))

    plt.suptitle("", y=1)
    plt.savefig("cfie_output.png", dpi=150, bbox_inches="tight",
                facecolor="#131722")
    plt.show()
    print("[저장] cfie_output.png")


# ──────────────────────────────────────────────
# 6. 메인
# ──────────────────────────────────────────────

PRESET_TICKERS = [
    ("005380.KS", "현대자동차"),
    ("INTC",      "Intel"),
    ("ORCL",      "Oracle"),
    ("META",      "Meta"),
    ("005930.KS", "삼성전자"),
    ("035720.KS", "카카오"),
    ("000660.KS", "SK하이닉스"),
    ("NVDA",      "NVIDIA"),
    ("TSLA",      "Tesla"),
    ("AAPL",      "Apple"),
]


def interactive_menu():
    print("\n" + "═" * 50)
    print("  CFIE v3.7 — 차트 첫인상 엔진")
    print("═" * 50)
    for i, (t, n) in enumerate(PRESET_TICKERS, 1):
        print(f"  {i:2d}. {t:<14} {n}")
    print("   0. 직접 입력")
    print("═" * 50)
    choice = input("선택 (번호 또는 0): ").strip()
    if choice == "0" or choice == "":
        ticker = input("티커 입력 (예: 005380.KS): ").strip().upper()
    else:
        idx = int(choice) - 1
        ticker = PRESET_TICKERS[idx][0]
    return ticker


def main():
    parser = argparse.ArgumentParser(description="CFIE v3.7")
    parser.add_argument("--ticker", type=str, default=None)
    parser.add_argument("--period", type=str, default="2y")
    parser.add_argument("--bars",   type=int, default=220,
                        help="차트에 표시할 봉 수")
    args = parser.parse_args()

    ticker = args.ticker or interactive_menu()
    print(f"\n[다운로드] {ticker} ({args.period})…")

    df = fetch(ticker, args.period)
    df = calc_indicators(df)
    df_fis = calc_fis(df)
    judgment = one_sentence(df_fis)

    fis = judgment["fis"]
    print(f"\n{'─'*50}")
    print(f"  첫인상: {judgment['label']}  FIS {fis:+.1f}")
    print(f"{'─'*50}")
    print(f"  {judgment['summary_l1']}")
    print(f"  {judgment['summary_l2']}")
    print(f"{'─'*50}")
    print("  세부 점수:")
    for k, v in judgment["scores"].items():
        bar = "█" * int(abs(v) / 2)
        sign = "+" if v >= 0 else ""
        print(f"    {k:8s} {sign}{v:5.1f}  {bar}")
    print(f"{'─'*50}\n")

    plot_chart(ticker, df_fis, judgment, display_bars=args.bars)


if __name__ == "__main__":
    main()
