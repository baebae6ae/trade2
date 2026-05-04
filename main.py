"""
main.py — CFIE v3.7 진입점
Flask 서버를 시작하고 기본 브라우저로 홈페이지를 엽니다.

실행:
    python main.py
"""

import os
import sys
import threading
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.server import create_app

PORT = 7860
URL  = f"http://127.0.0.1:{PORT}"


def open_browser():
    time.sleep(1.5)
    webbrowser.open(URL)


def main():
    app = create_app()
    print("=" * 52)
    print("  CFIE v3.7 — 차트 첫인상 엔진")
    print("=" * 52)
    print(f"  서버 주소: {URL}")
    print("  종료: Ctrl+C")
    print("=" * 52)
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, debug=False,
            use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
