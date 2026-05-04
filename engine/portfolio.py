"""engine/portfolio.py — 포트폴리오 관리 (portfolio.json 파일 기반)"""

import json
import os
from datetime import datetime

_BASE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_FILE = os.path.join(_BASE, "portfolio.json")


def _load() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        return {"positions": {}}
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"positions": {}}


def _save(data: dict):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_positions() -> dict:
    return _load().get("positions", {})


def buy(ticker: str, name: str, qty: int, price: float) -> dict:
    """신규 진입 또는 추가 매수. 평단가 가중평균 재계산."""
    if qty <= 0:
        raise ValueError("수량은 1 이상이어야 합니다.")
    if price <= 0:
        raise ValueError("매수가는 0보다 커야 합니다.")
    data = _load()
    pos  = data["positions"]
    if ticker in pos:
        old_qty = pos[ticker]["quantity"]
        old_avg = pos[ticker]["avg_price"]
        new_qty = old_qty + qty
        new_avg = round((old_avg * old_qty + price * qty) / new_qty, 4)
        pos[ticker]["quantity"]  = new_qty
        pos[ticker]["avg_price"] = new_avg
        pos[ticker]["buys"].append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "qty": qty, "price": price,
        })
    else:
        pos[ticker] = {
            "name":      name,
            "quantity":  qty,
            "avg_price": price,
            "buys": [{
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "qty": qty, "price": price,
            }],
        }
    _save(data)
    return pos[ticker]


def sell(ticker: str, qty: int) -> dict:
    """부분 매도(qty>0) 또는 전량 매도(qty=0)."""
    data = _load()
    pos  = data["positions"]
    if ticker not in pos:
        raise ValueError(f"보유 종목이 아닙니다: {ticker}")
    current  = pos[ticker]["quantity"]
    sell_qty = current if qty == 0 else qty
    if sell_qty <= 0:
        raise ValueError("매도 수량은 1 이상이어야 합니다.")
    if sell_qty >= current:
        del pos[ticker]
        _save(data)
        return {"sold_all": True, "ticker": ticker}
    pos[ticker]["quantity"] = current - sell_qty
    _save(data)
    return {"sold_all": False, "ticker": ticker, "remaining": pos[ticker]["quantity"]}
