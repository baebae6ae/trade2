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

# Render.com은 PORT 환경변수를 주입함. 로컬은 기본 7860.
PORT      = int(os.environ.get("PORT", 7860))
IS_CLOUD  = "PORT" in os.environ                 # Render에서 실행 중 여부
URL       = f"http://127.0.0.1:{PORT}"


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
    # 클라우드(Render)에서는 브라우저를 열지 않음
    if not IS_CLOUD:
        threading.Thread(target=open_browser, daemon=True).start()
    host = "0.0.0.0" if IS_CLOUD else "127.0.0.1"
    app.run(host=host, port=PORT, debug=False,
            use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
