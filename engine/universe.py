"""engine/universe.py — 검색/스캔/52주 신고가 공용 종목 풀"""

KOSPI = [
    ("005930.KS", "삼성전자"), ("000660.KS", "SK하이닉스"), ("005380.KS", "현대차"),
    ("005490.KS", "POSCO홀딩스"), ("035420.KS", "NAVER"), ("000270.KS", "기아"),
    ("051910.KS", "LG화학"), ("006400.KS", "삼성SDI"), ("028260.KS", "삼성물산"),
    ("012330.KS", "현대모비스"), ("207940.KS", "삼성바이오로직스"), ("032830.KS", "삼성생명"),
    ("035720.KS", "카카오"), ("055550.KS", "신한지주"), ("017670.KS", "SK텔레콤"),
    ("015760.KS", "한국전력"), ("066570.KS", "LG전자"), ("096770.KS", "SK이노베이션"),
    ("003550.KS", "LG"), ("009150.KS", "삼성전기"), ("000810.KS", "삼성화재"),
    ("086790.KS", "하나금융지주"), ("024110.KS", "기업은행"), ("033780.KS", "KT&G"),
    ("003490.KS", "대한항공"), ("010950.KS", "S-Oil"), ("316140.KS", "우리금융지주"),
    ("018260.KS", "삼성SDS"), ("011200.KS", "HMM"), ("034220.KS", "LG디스플레이"),
]

KOSDAQ = [
    ("247540.KQ", "에코프로비엠"), ("086520.KQ", "에코프로"), ("357780.KQ", "솔브레인"),
    ("145020.KQ", "휴젤"), ("066970.KQ", "엘앤에프"), ("263750.KQ", "펄어비스"),
    ("041510.KQ", "에스엠"), ("285130.KQ", "SK바이오사이언스"), ("048260.KQ", "오스템임플란트"),
    ("293480.KQ", "카카오게임즈"), ("196170.KQ", "알테오젠"), ("251270.KQ", "넷마블"),
    ("035900.KQ", "JYP Ent."), ("394280.KQ", "오픈엣지테크놀로지"), ("140860.KQ", "파크시스템스"),
    ("095340.KQ", "ISC"), ("211270.KQ", "AP시스템"), ("039030.KQ", "이오테크닉스"),
    ("112040.KQ", "위메이드"), ("091990.KQ", "셀트리온헬스케어"),
]

US = [
    ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "NVIDIA"),
    ("GOOGL", "Alphabet"), ("AMZN", "Amazon"), ("META", "Meta"),
    ("TSLA", "Tesla"), ("AVGO", "Broadcom"), ("JPM", "JPMorgan"),
    ("LLY", "Eli Lilly"), ("V", "Visa"), ("UNH", "UnitedHealth"),
    ("XOM", "Exxon"), ("MA", "Mastercard"), ("JNJ", "J&J"),
    ("PG", "P&G"), ("HD", "Home Depot"), ("COST", "Costco"),
    ("WMT", "Walmart"), ("BAC", "Bank of America"), ("CRM", "Salesforce"),
    ("ORCL", "Oracle"), ("NFLX", "Netflix"), ("AMD", "AMD"),
    ("INTC", "Intel"), ("KO", "Coca-Cola"), ("PEP", "PepsiCo"),
    ("DIS", "Disney"), ("ABBV", "AbbVie"), ("MRK", "Merck"),
]

MARKET_MAP = {
    "kospi": KOSPI,
    "kosdaq": KOSDAQ,
    "us": US,
}

ALL_STOCKS = KOSPI + KOSDAQ + US
NAME_MAP = {ticker: name for ticker, name in ALL_STOCKS}