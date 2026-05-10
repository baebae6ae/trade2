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
import matplotlib.transforms as mtransforms
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

EVENT_EXPLANATIONS = {
    "breakout": "긍정 신호: 최근 20봉 고점 저항을 종가로 돌파했습니다. 매도 물량이 있던 가격대를 넘겼다는 뜻이라, 추세가 한 단계 강해질 가능성이 큽니다.",
    "volume_spike": "상황 확인 신호(방향성은 캔들 확인): 평소보다 큰 거래량이 들어왔습니다. 거래량은 세력 참여를 뜻하므로, 양봉이면 상승 신뢰도↑, 음봉이면 분배/매물 소화 가능성↑입니다.",
    "ema20_reclaim": "긍정 신호: 단기 기준선(EMA20)을 다시 회복했습니다. 최근 눌림 이후 매수세가 재유입됐다는 의미라, 추세 재개 초기 구간으로 해석합니다.",
    "trailing_stop": "리스크 관리 기준선: 이 선 아래로 이탈하면 추세 훼손 가능성이 커집니다. 수익 구간에서는 이 값을 따라 손절 기준을 올리며 하락 전환을 빠르게 차단할 때 사용합니다.",
    "macd_golden": "긍정 신호: MACD가 시그널선을 상향 돌파해 모멘텀이 개선됐습니다. 하락 둔화 이후 상승 가속이 붙는 초기 전환 구간에서 자주 나타납니다.",
    "macd_dead": "부정 신호: MACD가 시그널선을 하향 이탈해 모멘텀이 약해졌습니다. 상승 탄력이 꺾였다는 뜻이라, 단기 조정 또는 추세 둔화 가능성을 경고합니다.",
}


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=BG)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _recent_true_indices(mask: pd.Series, limit: int = 3, lookback: int = 90) -> list[int]:
    if mask is None or len(mask) == 0:
        return []
    values = mask.fillna(False).to_numpy(dtype=bool)
    lower = max(0, len(values) - lookback)
    indices = [idx for idx, flag in enumerate(values) if flag and idx >= lower]
    return indices[-limit:]


def _annotate_price_events(ax, df: pd.DataFrame, indices: list[int], label: str,
                           color: str, above: bool = True) -> None:
    for idx in indices:
        row = df.iloc[idx]
        if above:
            marker_y = float(row["High"])
            marker = "^"
        else:
            marker_y = float(row["Low"])
            marker = "v"
        ax.scatter(idx, marker_y, s=42, marker=marker, color=color,
                   edgecolors=BG, linewidths=0.6, zorder=6)


def _annotate_macd_events(ax, df: pd.DataFrame, cross_up: pd.Series, cross_down: pd.Series) -> None:
    for idx in _recent_true_indices(cross_up, limit=2, lookback=120):
        y = max(float(df["MACD"].iloc[idx]), float(df["MACD_SIG"].iloc[idx]))
        ax.scatter(idx, y, s=34, marker="^", color=BULL, zorder=6)
    for idx in _recent_true_indices(cross_down, limit=2, lookback=120):
        y = min(float(df["MACD"].iloc[idx]), float(df["MACD_SIG"].iloc[idx]))
        ax.scatter(idx, y, s=34, marker="v", color=BEAR, zorder=6)


def _build_chart_events(df: pd.DataFrame) -> tuple[pd.Series | None, list[dict], pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    volume_ratio = pd.Series(np.nan, index=df.index, dtype=float)
    if "Vol20" in df.columns:
        volume_ratio = df["Volume"] / df["Vol20"].replace(0, np.nan)

    trailing_stop = None
    if "ATR14" in df.columns:
        trailing_stop = df["High"].rolling(20, min_periods=10).max() - (df["ATR14"] * 2.0)

    breakout_mask = pd.Series(False, index=df.index)
    if len(df) >= 20:
        prior_high20 = df["High"].rolling(20, min_periods=10).max().shift(1)
        breakout_mask = prior_high20.notna() & (df["Close"] >= prior_high20)
        if volume_ratio.notna().any():
            breakout_mask &= volume_ratio >= 1.15

    ema_reclaim_mask = pd.Series(False, index=df.index)
    if "EMA20" in df.columns:
        ema_reclaim_mask = (
            (df["Close"].shift(1) < df["EMA20"].shift(1))
            & (df["Close"] >= df["EMA20"])
            & (df["Close"] >= df["Open"])
        )

    volume_spike_mask = pd.Series(False, index=df.index)
    if volume_ratio.notna().any():
        volume_spike_mask = (
            (volume_ratio >= 1.8)
            & (df["Close"] >= df["Open"])
            & ~breakout_mask.fillna(False)
        )

    cross_up = pd.Series(False, index=df.index)
    cross_down = pd.Series(False, index=df.index)
    if "MACD" in df.columns and "MACD_SIG" in df.columns:
        cross_up = (df["MACD"] >= df["MACD_SIG"]) & (df["MACD"].shift(1) < df["MACD_SIG"].shift(1))
        cross_down = (df["MACD"] < df["MACD_SIG"]) & (df["MACD"].shift(1) >= df["MACD_SIG"].shift(1))

    events = []
    for idx in _recent_true_indices(breakout_mask, limit=3, lookback=120):
        events.append({
            "type": "breakout",
            "label": "돌파",
            "panel": "price",
            "idx": idx,
            "value": float(df["High"].iloc[idx]),
            "date": df.index[idx].strftime("%Y-%m-%d"),
            "color": BULL,
        })
    for idx in _recent_true_indices(volume_spike_mask, limit=2, lookback=90):
        events.append({
            "type": "volume_spike",
            "label": "거래량 급증",
            "panel": "volume",
            "idx": idx,
            "value": float(df["Volume"].iloc[idx]),
            "date": df.index[idx].strftime("%Y-%m-%d"),
            "color": "#8D6E63",
        })
    for idx in _recent_true_indices(ema_reclaim_mask & ~breakout_mask.fillna(False), limit=2, lookback=90):
        events.append({
            "type": "ema20_reclaim",
            "label": "EMA20 회복",
            "panel": "price",
            "idx": idx,
            "value": float(df["Low"].iloc[idx]),
            "date": df.index[idx].strftime("%Y-%m-%d"),
            "color": "#FF6F00",
        })
    for idx in _recent_true_indices(cross_up, limit=2, lookback=120):
        events.append({
            "type": "macd_golden",
            "label": "MACD 골든",
            "panel": "macd",
            "idx": idx,
            "value": max(float(df["MACD"].iloc[idx]), float(df["MACD_SIG"].iloc[idx])),
            "date": df.index[idx].strftime("%Y-%m-%d"),
            "color": BULL,
        })
    for idx in _recent_true_indices(cross_down, limit=2, lookback=120):
        events.append({
            "type": "macd_dead",
            "label": "MACD 데드",
            "panel": "macd",
            "idx": idx,
            "value": min(float(df["MACD"].iloc[idx]), float(df["MACD_SIG"].iloc[idx])),
            "date": df.index[idx].strftime("%Y-%m-%d"),
            "color": BEAR,
        })
    return trailing_stop, events, breakout_mask, ema_reclaim_mask, volume_spike_mask, cross_up, cross_down


def _axis_meta(ax, fig, y_invert: bool = True) -> dict:
    box = ax.get_position()
    top = 1.0 - float(box.y1) if y_invert else float(box.y0)
    bottom = 1.0 - float(box.y0) if y_invert else float(box.y1)
    return {
        "left": float(box.x0),
        "right": float(box.x1),
        "top": top,
        "bottom": bottom,
        "width": float(box.width),
        "height": float(box.height),
        "x_min": float(ax.get_xlim()[0]),
        "x_max": float(ax.get_xlim()[1]),
        "y_min": float(ax.get_ylim()[0]),
        "y_max": float(ax.get_ylim()[1]),
    }


def _event_meta(fig, ax, event: dict) -> dict:
    x_fig, y_fig = fig.transFigure.inverted().transform(ax.transData.transform((event["idx"], event["value"])))
    payload = dict(event)
    payload["x"] = float(x_fig)
    payload["y"] = 1.0 - float(y_fig)
    payload["description"] = EVENT_EXPLANATIONS.get(event["type"], "")
    return payload


def _draw_right_price_tag(ax, y: float, text: str, color: str) -> None:
    """가격 축 우측 끝에 수평선 라벨 표시."""
    trans = mtransforms.blended_transform_factory(ax.transAxes, ax.transData)
    ax.text(
        0.995, y, text,
        transform=trans,
        ha="right", va="center",
        fontsize=8.2, fontweight="bold", color="#FFFFFF",
        bbox=dict(facecolor=color, edgecolor=color, boxstyle="round,pad=0.18", alpha=0.94),
        zorder=8,
        clip_on=False,
    )


def render_main_chart(df_fis: pd.DataFrame, judgment: dict,
                      ticker: str, display_bars: int = 220,
                      timeframe: str = "daily", include_meta: bool = False,
                      holding_lines: dict | None = None):
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
        left=0.045, right=0.95,
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

    trailing_stop, events, breakout_mask, ema_reclaim_mask, volume_spike_mask, cross_up, cross_down = _build_chart_events(df)

    if trailing_stop is not None:
        ax_c.plot(xs, trailing_stop.values, color="#6D4C41", lw=0.9,
                  ls=":", alpha=0.9, label="추적손절", zorder=3)

    if holding_lines:
        avg_price = float(holding_lines.get("avg_price") or 0)
        hold_ts = float(holding_lines.get("trailing_stop") or 0)
        if avg_price > 0:
            ax_c.axhline(avg_price, color="#1976D2", lw=1.1, ls="-.", alpha=0.95, zorder=5, label="평단가")
            _draw_right_price_tag(ax_c, avg_price, f"평단 {avg_price:,.0f}", "#1976D2")
        if hold_ts > 0:
            ax_c.axhline(hold_ts, color="#8D6E63", lw=1.2, ls="--", alpha=0.95, zorder=5, label="보유 추적손절")
            _draw_right_price_tag(ax_c, hold_ts, f"TS {hold_ts:,.0f}", "#8D6E63")

    _annotate_price_events(ax_c, df, _recent_true_indices(breakout_mask, limit=3, lookback=120), "돌파", BULL, above=True)
    _annotate_price_events(ax_c, df, _recent_true_indices(ema_reclaim_mask & ~breakout_mask.fillna(False), limit=2, lookback=90), "EMA20 회복", "#FF6F00", above=False)

    ax_c.set_xlim(-1, n + 2)
    ax_c.legend(loc="upper left", fontsize=6.5,
                facecolor=BG2, edgecolor=GRID,
                labelcolor="#222222", ncol=8, framealpha=0.9)

    # ── 거래량 ──
    for i, (_, row) in enumerate(df.iterrows()):
        color = BULL_T if row["Close"] >= row["Open"] else BEAR_T
        ax_v.bar(i, row["Volume"], color=color, width=0.7)
    if "Vol20" in df.columns:
        ax_v.plot(xs, df["Vol20"].values, color=TEXT, lw=0.8)
    for idx in _recent_true_indices(volume_spike_mask, limit=2, lookback=90):
        y = float(df["Volume"].iloc[idx])
        ax_v.scatter(idx, y, s=34, marker="^", color="#8D6E63", zorder=6)
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
        _annotate_macd_events(ax_m, df, cross_up, cross_down)
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
    if include_meta:
        panels = {
            "price": _axis_meta(ax_c, fig),
            "volume": _axis_meta(ax_v, fig),
            "macd": _axis_meta(ax_m, fig),
            "fis": _axis_meta(ax_f, fig),
        }
        interaction_meta = {
            "count": n,
            "dates": [ts.strftime("%Y-%m-%d") for ts in df.index],
            "panels": panels,
            "plot_area": {
                "left": panels["price"]["left"],
                "right": panels["price"]["right"],
                "top": panels["price"]["top"],
                "bottom": panels["fis"]["bottom"],
            },
            "events": [
                _event_meta(fig, {"price": ax_c, "volume": ax_v, "macd": ax_m}[event["panel"]], event)
                for event in events
                if event["panel"] in {"price", "volume", "macd"}
            ],
        }
    plt.close(fig)
    if include_meta:
        return b64, interaction_meta
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

