"""engine/portfolio.py — 포트폴리오 관리 (portfolio.json 파일 기반 + GitHub 동기화)"""

import base64
import json
import os
import threading
from datetime import datetime

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

_BASE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_FILE = os.path.join(_BASE, "portfolio.json")

_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
_GITHUB_REPO  = os.getenv("GITHUB_REPO",  "")   # ex) "baebae6ae/trade2"
_GITHUB_PATH  = "portfolio.json"
_GITHUB_BRANCH = "main"


def _gh_url() -> str:
    return f"https://api.github.com/repos/{_GITHUB_REPO}/contents/{_GITHUB_PATH}"


def _gh_headers() -> dict:
    return {"Authorization": f"token {_GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"}


def _pull_from_github() -> bool:
    """GitHub에서 portfolio.json 내려받아 로컬에 저장. 성공 시 True."""
    if not (_HAS_REQUESTS and _GITHUB_TOKEN and _GITHUB_REPO):
        return False
    try:
        r = _req.get(_gh_url(), headers=_gh_headers(), timeout=10)
        if r.status_code == 200:
            raw = base64.b64decode(r.json()["content"]).decode("utf-8")
            with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
                f.write(raw)
            return True
    except Exception:
        pass
    return False


def _push_to_github(content: str):
    """portfolio.json 내용을 GitHub에 커밋 (백그라운드 스레드에서 호출)."""
    if not (_HAS_REQUESTS and _GITHUB_TOKEN and _GITHUB_REPO):
        return
    try:
        url = _gh_url()
        hdrs = _gh_headers()
        r = _req.get(url, headers=hdrs, timeout=10)
        sha = r.json().get("sha") if r.status_code == 200 else None
        body: dict = {
            "message": "auto: portfolio update",
            "content": base64.b64encode(content.encode("utf-8")).decode(),
            "branch":  _GITHUB_BRANCH,
        }
        if sha:
            body["sha"] = sha
        _req.put(url, json=body, headers=hdrs, timeout=15)
    except Exception:
        pass


def _load() -> dict:
    # 로컬 파일 없으면 GitHub에서 복구 시도 (Render 재시작 대비)
    if not os.path.exists(PORTFOLIO_FILE):
        _pull_from_github()
    if not os.path.exists(PORTFOLIO_FILE):
        return {"positions": {}}
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"positions": {}}


def _save(data: dict):
    content = json.dumps(data, ensure_ascii=False, indent=2)
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    # 응답 지연 없이 백그라운드에서 GitHub 동기화
    threading.Thread(target=_push_to_github, args=(content,), daemon=True).start()


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
            "name":               name,
            "quantity":           qty,
            "avg_price":          price,
            "max_trailing_stop":  None,   # 래칫: 한번 올라간 손절선은 안 내려옴
            "buys": [{
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "qty": qty, "price": price,
            }],
        }
    _save(data)
    return pos[ticker]


def update_trailing_stop(ticker: str, new_ts: float) -> float | None:
    """래칫 방식으로 max_trailing_stop 갱신. 새 값이 더 크면 저장하고 반환."""
    data = _load()
    pos  = data["positions"]
    if ticker not in pos:
        return None
    current_max = pos[ticker].get("max_trailing_stop") or 0
    if new_ts > current_max:
        pos[ticker]["max_trailing_stop"] = round(new_ts, 4)
        _save(data)
        return round(new_ts, 4)
    return current_max if current_max > 0 else None


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
