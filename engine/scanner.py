"""engine/scanner.py — 신규 진입 후보 종목 스캐너"""

import concurrent.futures
import numpy as np
from engine.data import fetch, calc_indicators
from engine.fis  import calc_fis, make_judgment, calc_entry_score


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
        entry_data  = calc_entry_score(df_fis)
        entry_score = float(entry_data["score"])
        close_v     = float(last["Close"])
        ema20_v     = float(last.get("EMA20", close_v))
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
            "ichimoku":     j["ichimoku_status"],
            "summary_l1":   j["summary_l1"],
            "ok": True,
        }
    except Exception as e:
        return {"ticker": ticker, "name": name, "ok": False, "error": str(e)}


def scan_market(market: str) -> list:
    """
    지정 시장 전체 스캔 -> 신규 진입 후보

        필터:
            FIS ≥ 30 AND entry_score ≥ 55 AND risk > -16 AND trend > 0
            → '상승 우위가 유지되면서 눌림 품질이 양호한 종목'

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
        and r["entry_score"] >= 55
        and r["risk"] > -16
        and r["trend"] > 0
    ]
    candidates.sort(key=lambda x: x["entry_score"], reverse=True)
    return candidates
