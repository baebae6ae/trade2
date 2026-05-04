"""engine/scanner.py — 신규 진입 후보 종목 스캐너"""

import concurrent.futures
import numpy as np
from engine.data import fetch, calc_indicators
from engine.fis  import calc_fis, make_judgment


def _calc_entry_score(df_fis) -> float:
    """
    진입 타이밍 점수 (-10 ~ +30)

    FIS가 높다 = '지금 강하다'
    Entry Score가 높다 = '강한 추세 중에서 지금 쉬고 있다' (눌림목/횡보)

    구성:
      EMA20 이격률   : ≤2% → +12 / ≤5% → +6 / >10% → -5  (이격 작을수록 눌림 완료)
      최근 5봉 조정폭: 3~12% 조정 → +10 / >15% 과락 → -5  (적정 조정이 있었는가)
      52주 위치      : 65~90% → +8 / 90~95% → +3 / >95% → -4  (저항 근접 감점)
    """
    last = df_fis.iloc[-1]
    c    = float(last["Close"])
    entry = 0.0

    # 1. EMA20 이격률 — 눌림 감지 (방향 포함)
    #    abs() 대신 방향 포함: 위쪽 이격이면 아직 안 눌렸을 수도 있음
    ema20 = float(last["EMA20"])
    if ema20 > 0:
        gap_pct = (c - ema20) / ema20 * 100   # 양수=위, 음수=아래
        if -2 <= gap_pct <= 3:   entry += 12  # EMA20 근접 (눌림 완료 구간)
        elif gap_pct <= 6:       entry += 6   # 약간 위 (아직 여유)
        elif gap_pct <= 12:      entry += 0   # 다소 이격
        elif gap_pct > 12:       entry -= 5   # 과열 — 아직 EMA 안 눌렸음
        elif gap_pct < -5:       entry -= 3   # 너무 아래 (추세 훼손 가능)

    # 2. 최근 5봉 고점 대비 조정 여부 — 이전 고점에서 얼마나 빠졌는가
    if len(df_fis) >= 6:
        recent_high = float(df_fis.iloc[-6:-1]["High"].max())
        if recent_high > 0:
            pullback_pct = (recent_high - c) / recent_high * 100
            if 3 <= pullback_pct <= 12:   entry += 10   # 적정 눌림
            elif pullback_pct > 15:       entry -= 5    # 너무 많이 빠짐 (추세 훼손 가능)

    # 3. 52주 고저 위치 — sweet spot 65~90%
    h52 = float(last["High52"])
    l52 = float(last["Low52"])
    rng = h52 - l52
    if rng > 0:
        pos52 = (c - l52) / rng * 100
        if 65 <= pos52 <= 90:    entry += 8    # 상위권, 저항 여유 있음
        elif 90 < pos52 <= 95:   entry += 3
        elif pos52 > 95:         entry -= 4    # 52주 고점 저항권
        # 60% 미만은 가점 없음 (추세 약함)

    return float(np.clip(entry, -10, 30))

KOSPI = [
    ("005930.KS","삼성전자"),("000660.KS","SK하이닉스"),("005380.KS","현대차"),
    ("005490.KS","POSCO홀딩스"),("035420.KS","NAVER"),("000270.KS","기아"),
    ("051910.KS","LG화학"),("006400.KS","삼성SDI"),("028260.KS","삼성물산"),
    ("012330.KS","현대모비스"),("207940.KS","삼성바이오로직스"),("032830.KS","삼성생명"),
    ("035720.KS","카카오"),("055550.KS","신한지주"),("017670.KS","SK텔레콤"),
    ("015760.KS","한국전력"),("066570.KS","LG전자"),("096770.KS","SK이노베이션"),
    ("003550.KS","LG"),("009150.KS","삼성전기"),("000810.KS","삼성화재"),
    ("086790.KS","하나금융지주"),("024110.KS","기업은행"),("033780.KS","KT&G"),
    ("003490.KS","대한항공"),("010950.KS","S-Oil"),("316140.KS","우리금융지주"),
    ("018260.KS","삼성SDS"),("011200.KS","HMM"),("034220.KS","LG디스플레이"),
]

KOSDAQ = [
    ("247540.KQ","에코프로비엠"),("086520.KQ","에코프로"),("357780.KQ","솔브레인"),
    ("145020.KQ","휴젤"),("066970.KQ","엘앤에프"),("263750.KQ","펄어비스"),
    ("041510.KQ","에스엠"),("285130.KQ","SK바이오사이언스"),("048260.KQ","오스템임플란트"),
    ("293480.KQ","카카오게임즈"),("196170.KQ","알테오젠"),("251270.KQ","넷마블"),
    ("035900.KQ","JYP Ent."),("394280.KQ","오픈엣지테크놀로지"),("140860.KQ","파크시스템스"),
    ("095340.KQ","ISC"),("211270.KQ","AP시스템"),("039030.KQ","이오테크닉스"),
    ("112040.KQ","위메이드"),("091990.KQ","셀트리온헬스케어"),
]

US = [
    ("AAPL","Apple"),("MSFT","Microsoft"),("NVDA","NVIDIA"),
    ("GOOGL","Alphabet"),("AMZN","Amazon"),("META","Meta"),
    ("TSLA","Tesla"),("AVGO","Broadcom"),("JPM","JPMorgan"),
    ("LLY","Eli Lilly"),("V","Visa"),("UNH","UnitedHealth"),
    ("XOM","Exxon"),("MA","Mastercard"),("JNJ","J&J"),
    ("PG","P&G"),("HD","Home Depot"),("COST","Costco"),
    ("WMT","Walmart"),("BAC","Bank of America"),("CRM","Salesforce"),
    ("ORCL","Oracle"),("NFLX","Netflix"),("AMD","AMD"),
    ("INTC","Intel"),("KO","Coca-Cola"),("PEP","PepsiCo"),
    ("DIS","Disney"),("ABBV","AbbVie"),("MRK","Merck"),
]

MARKET_MAP = {"kospi": KOSPI, "kosdaq": KOSDAQ, "us": US}


def _analyze_one(ticker_name):
    ticker, name = ticker_name
    try:
        df     = fetch(ticker, "1y")
        df     = calc_indicators(df)
        df_fis = calc_fis(df)
        j      = make_judgment(df_fis)
        last        = df_fis.iloc[-1]
        entry_score = _calc_entry_score(df_fis)
        return {
            "ticker":       ticker,
            "name":         name,
            "fis":          j["fis"],
            "label":        j["label"],
            "label_color":  j["label_color"],
            "close":        float(last["Close"]),
            "trend":        float(last["TrendScore"]),
            "momentum":     float(last["MomentumScore"]),
            "structure":    float(last["StructureScore"]),
            "compression":  float(last["CompressionScore"]),
            "volume":       float(last["VolumeScore"]),
            "risk":         float(last["RiskPenalty"]),
            "entry_score":  entry_score,
            "ichimoku":     j["ichimoku_status"],
            "summary_l1":   j["summary_l1"],
            "ok": True,
        }
    except Exception as e:
        return {"ticker": ticker, "name": name, "ok": False, "error": str(e)}


def scan_market(market: str) -> list:
    """
    지정 시장 전체 스캔 -> 신규 진입 후보

    필터 (이전 → 개선):
      이전: FIS ≥ 40 AND trend ≥ 10 AND risk > -15  (= 많이 오른 순)
      개선: FIS ≥ 30 AND entry_score ≥ 8 AND risk > -8 AND momentum < 18
            → '강한 추세에 있지만 지금 눌림/횡보 중인 종목'

    정렬: entry_score 높은 순 (눌림 품질 우선)
    """
    stocks = MARKET_MAP.get(market.lower(), [])
    if not stocks:
        return []
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(_analyze_one, stocks):
            if r["ok"]:
                results.append(r)
    candidates = [
        r for r in results
        if r["fis"] >= 30
        and r["entry_score"] >= 8
        and r["risk"] > -8
        and r["momentum"] < 18
    ]
    candidates.sort(key=lambda x: x["entry_score"], reverse=True)
    return candidates
