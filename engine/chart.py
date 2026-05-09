"""
engine/chart.py
Matplotlib 캔들차트 → base64 PNG 변환 모듈
(파일 저장 없이 메모리에서 직접 인코딩)
"""

import io
import base64
import os
import urllib.request
import tempfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

def _setup_korean_font():
    """Render/Linux 환경에서 한글 폰트 자동 다운로드 및 등록"""
    import matplotlib.font_manager as fm
    for font in fm.fontManager.ttflist:
        if any(k in font.name for k in ["Nanum", "Malgun", "Apple SD Gothic"]):
            matplotlib.rcParams["font.family"] = [font.name, "DejaVu Sans"]
            return
    dest = os.path.join(tempfile.gettempdir(), "NanumGothic.ttf")
    if not os.path.exists(dest):
        try:
            urllib.request.urlretrieve(
                "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf",
                dest
            )
        except Exception:
            return
    if os.path.exists(dest):
        try:
            fm.fontManager.addfont(dest)
        except AttributeError:
            pass
        matplotlib.rcParams["font.family"] = ["NanumGothic", "DejaVu Sans"]

_setup_korean_font()
matplotlib.rcParams["axes.unicode_minus"] = False

BG       = "#F9F9F7"
BG2      = "#F1F1ED"
BG3      = "#F6F6F2"
GRID     = "#D8D8D2"
TEXT     = "#303030"
BULL     = "#0D7F3C"
BEAR     = "#C41D3A"
BULL_T   = "#0D7F3C80"
BEAR_T   = "#C41D3A80"


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=BG)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def render_main_chart(df_fis: pd.DataFrame, judgment: dict,
                      ticker: str, display_bars: int = 220,
                      timeframe: str = "daily") -> str:
    """
    캔들 + 이동평균 + 볼린저 + 일목균형표 + 거래량 + MACD + RSI + FIS
    → base64 PNG 문자열 반환
    """
    df = df_fis.iloc[-display_bars:].copy()
    n  = len(df)
    xs = np.arange(n)
    timeframe_label_map = {
        "daily": "일봉",
        "weekly": "주봉",
        "monthly": "월봉",
        "yearly": "년봉",
    }
    date_fmt_map = {
        "daily": "%y/%m/%d",
        "weekly": "%y/%m",
        "monthly": "%Y/%m",
        "yearly": "%Y",
    }
    timeframe_label = timeframe_label_map.get(timeframe, "일봉")
    date_fmt = date_fmt_map.get(timeframe, "%y/%m/%d")

    fig = plt.figure(figsize=(16, 11), facecolor=BG)
    gs  = gridspec.GridSpec(
        4, 1,
        height_ratios=[5, 1, 1, 1],
        hspace=0.04,
        left=0.045, right=0.985,
        top=0.96, bottom=0.05
    )
    ax_c = fig.add_subplot(gs[0])
    ax_v = fig.add_subplot(gs[1], sharex=ax_c)
    ax_m = fig.add_subplot(gs[2], sharex=ax_c)
    ax_f = fig.add_subplot(gs[3], sharex=ax_c)

    for ax in [ax_c, ax_v, ax_m, ax_f]:
        ax.set_facecolor(BG)
        ax.tick_params(colors=TEXT, labelsize=9)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)
        ax.yaxis.tick_right()
        ax.grid(axis="y", color=GRID, lw=0.6, alpha=0.9)

    # ── 캔들 ──
    for i, (_, row) in enumerate(df.iterrows()):
        o, h, lo, c = row["Open"], row["High"], row["Low"], row["Close"]
        color = BULL if c >= o else BEAR
        ax_c.plot([i, i], [lo, h], color=color, lw=0.8, zorder=2)
        rect = plt.Rectangle(
            (i - 0.35, min(o, c)), 0.7,
            max(abs(c - o), 0.001 * c),
            color=color, zorder=3
        )
        ax_c.add_patch(rect)

    # ── 이동평균 ──
    ma_styles = [
        ("EMA5",   "#F6C90E", 0.8,  "EMA5"),
        ("EMA20",  "#FF6F00", 1.1,  "EMA20"),
        ("EMA60",  "#7E57C2", 1.3,  "EMA60"),
        ("EMA120", "#26A69A", 1.1,  "EMA120"),
    ]
    for col, clr, lw, lbl in ma_styles:
        if col in df.columns:
            ax_c.plot(xs, df[col].values, color=clr, lw=lw, label=lbl, zorder=4)

    # ── 볼린저밴드 ──
    if "BB_UP" in df.columns:
        ax_c.plot(xs, df["BB_UP"].values, color="#78909C", lw=0.7, ls="--", label="BB")
        ax_c.plot(xs, df["BB_DN"].values, color="#78909C", lw=0.7, ls="--")
        ax_c.fill_between(xs, df["BB_UP"].values, df["BB_DN"].values,
                          alpha=0.04, color="#78909C")

    # ── 일목균형표 — 캔들 위에 오버레이 ──
    if all(col in df.columns for col in ["ICH_TENKAN", "ICH_KIJUN",
                                          "ICH_SENKOU_A", "ICH_SENKOU_B"]):
        ax_c.fill_between(
            xs,
            df["ICH_SENKOU_A"].values,
            df["ICH_SENKOU_B"].values,
            where=df["ICH_SENKOU_A"].values >= df["ICH_SENKOU_B"].values,
            alpha=0.30, color=BULL, zorder=1, label="구름(상승)"
        )
        ax_c.fill_between(
            xs,
            df["ICH_SENKOU_A"].values,
            df["ICH_SENKOU_B"].values,
            where=df["ICH_SENKOU_A"].values < df["ICH_SENKOU_B"].values,
            alpha=0.30, color=BEAR, zorder=1, label="구름(하락)"
        )
        ax_c.plot(xs, df["ICH_TENKAN"].values,
                  color="#F44336", lw=0.85, ls="-.", label="전환", zorder=4)
        ax_c.plot(xs, df["ICH_KIJUN"].values,
                  color="#2196F3", lw=0.85, ls="-.", label="기준", zorder=4)

    ax_c.set_xlim(-1, n + 1)
    ax_c.legend(loc="upper left", fontsize=6.5,
                facecolor=BG2, edgecolor=GRID,
                labelcolor="#222222", ncol=8, framealpha=0.9)

    # ── 거래량 ──
    for i, (_, row) in enumerate(df.iterrows()):
        color = BULL_T if row["Close"] >= row["Open"] else BEAR_T
        ax_v.bar(i, row["Volume"], color=color, width=0.7)
    if "Vol20" in df.columns:
        ax_v.plot(xs, df["Vol20"].values, color=TEXT, lw=0.8)
    ax_v.set_ylabel("거래량", color=TEXT, fontsize=8)
    ax_v.yaxis.set_ticklabels([])

    # ── MACD ──
    if "MACD" in df.columns:
        ax_m.plot(xs, df["MACD"].values,     color="#42A5F5", lw=0.9, label="MACD")
        ax_m.plot(xs, df["MACD_SIG"].values, color="#EF5350", lw=0.9, label="Signal")
        hist = df["MACD_HIST"].values
        colors_h = [BULL if v >= 0 else BEAR for v in hist]
        ax_m.bar(xs, hist, color=colors_h, width=0.7, alpha=0.6)
        ax_m.axhline(0, color=GRID, lw=0.6)
        ax_m.legend(loc="upper left", fontsize=6,
                    facecolor=BG2, edgecolor=GRID,
                    labelcolor="#222222", ncol=2, framealpha=0.9)
    ax_m.set_ylabel("MACD", color=TEXT, fontsize=8)

    # ── FIS 히스토그램 ──
    fis_vals = df["FIS"].values
    for i, fv in enumerate(fis_vals):
        ax_f.bar(i, fv, color=BULL if fv >= 0 else BEAR, width=0.7, alpha=0.85)
    ax_f.axhline(0,   color=TEXT, lw=0.5)
    ax_f.axhline(40,  color=BULL, lw=0.4, ls="--", alpha=0.5)
    ax_f.axhline(-40, color=BEAR, lw=0.4, ls="--", alpha=0.5)
    ax_f.set_ylim(-100, 100)
    ax_f.set_ylabel("FIS", color=TEXT, fontsize=8)

    # X축 날짜
    step      = max(1, n // 12)
    tick_pos  = list(range(0, n, step))
    tick_labs = [df.index[i].strftime(date_fmt) for i in tick_pos]
    ax_f.set_xticks(tick_pos)
    ax_f.set_xticklabels(tick_labs, color=TEXT, fontsize=9, rotation=15)
    for ax in [ax_c, ax_v, ax_m]:
        plt.setp(ax.get_xticklabels(), visible=False)

    # 우측 오버레이는 제거하고 사이드바 판단 패널을 사용한다.

    # 종목명 + 현재가 + 첫인상 레이블
    last_close = float(df_fis.iloc[-1]["Close"])
    label = judgment["label"]
    lcolor = judgment["label_color"]
    ax_c.text(0.01, 0.98, label,
              transform=ax_c.transAxes,
              va="top", ha="left",
              color=lcolor, fontsize=13, fontweight="bold",
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.75, pad=2))
    ax_c.text(0.01, 0.90, f"{ticker} [{timeframe_label}]  {last_close:,.2f}",
              transform=ax_c.transAxes,
              va="top", ha="left",
              color=TEXT, fontsize=10.5,
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.6, pad=2))

    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def render_mini_chart(df: pd.DataFrame, ticker: str, fis: float) -> str:
    """대시보드용 미니 캔들 차트 (최근 60봉)"""
    df = df.iloc[-60:].copy()
    n  = len(df)
    xs = np.arange(n)

    fig, ax = plt.subplots(figsize=(4, 1.8), facecolor=BG)
    ax.set_facecolor(BG)
    ax.axis("off")

    for i, (_, row) in enumerate(df.iterrows()):
        o, h, lo, c = row["Open"], row["High"], row["Low"], row["Close"]
        color = BULL if c >= o else BEAR
        ax.plot([i, i], [lo, h], color=color, lw=0.6)
        ax.add_patch(plt.Rectangle(
            (i - 0.35, min(o, c)), 0.7,
            max(abs(c - o), 0.001 * abs(c)),
            color=color
        ))

    if "EMA20" in df.columns:
        ax.plot(xs, df["EMA20"].values, color="#FF6F00", lw=1.0)

    ax.set_xlim(-1, n + 1)
    fig.tight_layout(pad=0)
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64

