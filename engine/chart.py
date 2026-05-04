"""
engine/chart.py
Matplotlib 캔들차트 → base64 PNG 변환 모듈
(파일 저장 없이 메모리에서 직접 인코딩)
"""

import io
import base64
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

matplotlib.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

BG       = "#131722"
BG2      = "#1E222D"
BG3      = "#1A1E2E"
GRID     = "#2A2E39"
TEXT     = "#B2B5BE"
BULL     = "#E53935"
BEAR     = "#1E88E5"
BULL_T   = "#E5393580"
BEAR_T   = "#1E88E580"


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=BG)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def render_main_chart(df_fis: pd.DataFrame, judgment: dict,
                      ticker: str, display_bars: int = 220) -> str:
    """
    캔들 + 이동평균 + 볼린저 + 일목균형표 + 거래량 + MACD + RSI + FIS
    → base64 PNG 문자열 반환
    """
    df = df_fis.iloc[-display_bars:].copy()
    n  = len(df)
    xs = np.arange(n)

    fig = plt.figure(figsize=(16, 11), facecolor=BG)
    gs  = gridspec.GridSpec(
        5, 1,
        height_ratios=[4, 1, 1, 1, 1],
        hspace=0.04,
        left=0.04, right=0.86,
        top=0.96, bottom=0.05
    )
    ax_c  = fig.add_subplot(gs[0])
    ax_ich = fig.add_subplot(gs[1], sharex=ax_c)
    ax_v  = fig.add_subplot(gs[2], sharex=ax_c)
    ax_m  = fig.add_subplot(gs[3], sharex=ax_c)
    ax_f  = fig.add_subplot(gs[4], sharex=ax_c)

    for ax in [ax_c, ax_ich, ax_v, ax_m, ax_f]:
        ax.set_facecolor(BG)
        ax.tick_params(colors=TEXT, labelsize=7.5)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)
        ax.yaxis.tick_right()
        ax.grid(axis="y", color=GRID, lw=0.4, alpha=0.6)

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

    ax_c.set_xlim(-1, n + 1)
    ax_c.legend(loc="upper left", fontsize=6.5,
                facecolor=BG2, edgecolor=GRID,
                labelcolor="white", ncol=6, framealpha=0.8)

    # ── 일목균형표 패널 ──
    if all(c in df.columns for c in ["ICH_TENKAN", "ICH_KIJUN",
                                      "ICH_SENKOU_A", "ICH_SENKOU_B"]):
        ax_ich.fill_between(
            xs,
            df["ICH_SENKOU_A"].values,
            df["ICH_SENKOU_B"].values,
            where=df["ICH_SENKOU_A"].values >= df["ICH_SENKOU_B"].values,
            alpha=0.3, color=BULL, label="구름(상승)"
        )
        ax_ich.fill_between(
            xs,
            df["ICH_SENKOU_A"].values,
            df["ICH_SENKOU_B"].values,
            where=df["ICH_SENKOU_A"].values < df["ICH_SENKOU_B"].values,
            alpha=0.3, color=BEAR, label="구름(하락)"
        )
        ax_ich.plot(xs, df["ICH_TENKAN"].values, color="#F44336", lw=0.9, label="전환선")
        ax_ich.plot(xs, df["ICH_KIJUN"].values,  color="#2196F3", lw=0.9, label="기준선")
        ax_ich.legend(loc="upper left", fontsize=6,
                      facecolor=BG2, edgecolor=GRID,
                      labelcolor="white", ncol=4, framealpha=0.8)
    ax_ich.set_ylabel("일목", color=TEXT, fontsize=6.5)

    # ── 거래량 ──
    for i, (_, row) in enumerate(df.iterrows()):
        color = BULL_T if row["Close"] >= row["Open"] else BEAR_T
        ax_v.bar(i, row["Volume"], color=color, width=0.7)
    if "Vol20" in df.columns:
        ax_v.plot(xs, df["Vol20"].values, color=TEXT, lw=0.8)
    ax_v.set_ylabel("거래량", color=TEXT, fontsize=6.5)
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
                    labelcolor="white", ncol=2, framealpha=0.8)
    ax_m.set_ylabel("MACD", color=TEXT, fontsize=6.5)

    # ── FIS 히스토그램 ──
    fis_vals = df["FIS"].values
    for i, fv in enumerate(fis_vals):
        ax_f.bar(i, fv, color=BULL if fv >= 0 else BEAR, width=0.7, alpha=0.85)
    ax_f.axhline(0,   color=TEXT, lw=0.5)
    ax_f.axhline(40,  color=BULL, lw=0.4, ls="--", alpha=0.5)
    ax_f.axhline(-40, color=BEAR, lw=0.4, ls="--", alpha=0.5)
    ax_f.set_ylim(-100, 100)
    ax_f.set_ylabel("FIS", color=TEXT, fontsize=6.5)

    # X축 날짜
    step      = max(1, n // 12)
    tick_pos  = list(range(0, n, step))
    tick_labs = [df.index[i].strftime("%y/%m/%d") for i in tick_pos]
    ax_f.set_xticks(tick_pos)
    ax_f.set_xticklabels(tick_labs, color=TEXT, fontsize=7.5, rotation=15)
    for ax in [ax_c, ax_ich, ax_v, ax_m]:
        plt.setp(ax.get_xticklabels(), visible=False)

    # ── CFIE 판단 오버레이 (우측) ──
    fis      = judgment["fis"]
    lcolor   = judgment["label_color"]
    label    = judgment["label"]
    sl1      = judgment["summary_l1"]
    sl2      = judgment["summary_l2"]

    # 헤더 박스
    bx, by, bw, bh = 0.865, 0.965, 0.132, 0.028
    hax = fig.add_axes([bx, by, bw, bh])
    hax.set_facecolor(BG2); hax.axis("off")
    hax.text(0.04, 0.5, "CFIE v3.7", va="center", ha="left",
             color=TEXT, fontsize=8, fontweight="bold",
             transform=hax.transAxes)
    hax.text(0.5, 0.5, "한문장 판단", va="center", ha="center",
             color="white", fontsize=9, fontweight="bold",
             transform=hax.transAxes)
    hax.text(0.97, 0.5, f"FIS {fis:+.0f}", va="center", ha="right",
             color=lcolor, fontsize=8.5, fontweight="bold",
             transform=hax.transAxes)

    # 요약 본문 박스
    body_h = 0.20
    bax = fig.add_axes([bx, by - body_h, bw, body_h])
    bax.set_facecolor(BG3); bax.axis("off")

    chip = FancyBboxPatch(
        (0.02, 0.66), 0.96, 0.28,
        boxstyle="round,pad=0.01",
        facecolor=lcolor, edgecolor="none",
        transform=bax.transAxes
    )
    bax.add_patch(chip)
    bax.text(0.5, 0.80, label, va="center", ha="center",
             color="white", fontsize=9.5, fontweight="bold",
             transform=bax.transAxes)

    # 요약 텍스트 (줄 자동 분리)
    def wrap_text(ax, text, y, fs=7.2):
        ax.text(0.03, y, text, va="top", ha="left",
                color="#E0E3EB", fontsize=fs,
                transform=ax.transAxes,
                wrap=True,
                multialignment="left")

    wrap_text(bax, sl1, 0.62)
    wrap_text(bax, sl2, 0.34)

    # 세부 점수 바 (하단 박스)
    scores   = judgment["scores"]
    keys     = list(scores.keys())
    vals     = [scores[k] for k in keys]
    bar_clrs = [BULL if v >= 0 else BEAR for v in vals]

    score_h = 0.14
    sax = fig.add_axes([bx, by - body_h - score_h - 0.01, bw, score_h])
    sax.set_facecolor(BG3)
    sax.barh(keys, vals, color=bar_clrs, height=0.6)
    sax.axvline(0, color=TEXT, lw=0.6)
    sax.set_xlim(-32, 32)
    sax.tick_params(colors=TEXT, labelsize=7)
    for sp in sax.spines.values():
        sp.set_visible(False)
    sax.yaxis.tick_left()
    sax.set_facecolor(BG3)

    # 종목명 + 현재가 + 첫인상 레이블
    last_close = float(df_fis.iloc[-1]["Close"])
    ax_c.text(0.01, 0.98, label,
              transform=ax_c.transAxes,
              va="top", ha="left",
              color=lcolor, fontsize=12, fontweight="bold",
              bbox=dict(facecolor=BG, edgecolor="none", alpha=0.75, pad=2))
    ax_c.text(0.01, 0.90, f"{ticker}  {last_close:,.2f}",
              transform=ax_c.transAxes,
              va="top", ha="left",
              color=TEXT, fontsize=9.5,
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
