# trade2

CFIE v3.7 기반의 Flask 주식 분석 웹앱입니다.

이 프로젝트는 Yahoo Finance 시세 데이터를 바탕으로 차트 첫인상 점수(FIS), 진입 점수, 시장 스캔, 포트폴리오 손익과 포트폴리오 자체 분석을 제공합니다.

## 주요 기능

- 종목 차트 분석: `/analyze`
- 신규 진입 후보 스캔: `/scan`
- 내 포트폴리오 관리: `/mypage`
- 분석 API: `/api/analyze/<ticker>`
- 시장 스캔 API: `/api/scan/<market>`
- 포트폴리오 조회/매수/매도 API: `/api/portfolio`, `/api/portfolio/buy`, `/api/portfolio/sell`

## 분석 기능

- FIS(First Impression Score) 기반 차트 상태 평가
- 진입 점수 기반 타이밍 평가
- 일봉, 주봉, 월봉, 년봉 멀티 타임프레임 분석
- 메인 차트 이미지와 최근 지표 테이블 제공
- 포트폴리오 보유 종목별 FIS, 진입 점수, 위험도 계산
- 포트폴리오 전체 가중 FIS, 가중 진입 점수, 분산도 분석

## 기술 스택

- Python
- Flask
- pandas
- numpy
- matplotlib
- yfinance

## 설치

```bash
pip install -r requirements.txt
```

권장 Python 버전은 `3.11` 입니다. Render 설정도 Python `3.11.0` 기준입니다.

## 실행

로컬 실행:

```bash
python main.py
```

기본 접속 주소:

```text
http://127.0.0.1:7860
```

배포 환경에서는 `PORT` 환경변수를 사용합니다.

## API 메모

`/api/analyze/<ticker>`는 다음과 같은 쿼리 파라미터를 사용합니다.

- `period`: 기본값 `2y`
- `timeframe`: `daily`, `weekly`, `monthly`, `yearly`
- `bars`: 기본값 `220`

응답에는 차트 이미지, 판단 결과, 최근 테이블, 진입 점수, 최신 지표가 포함됩니다.

`/api/portfolio`는 보유 종목 목록과 손익 요약뿐 아니라 포트폴리오 전체 분석 결과도 반환합니다.

## 데이터 저장

- 포트폴리오 데이터는 루트의 `portfolio.json` 파일에 저장됩니다.
- 이 파일은 개인 데이터이므로 `.gitignore`에 포함되어 있습니다.

## 배포

Render 배포 설정은 `render.yaml`에 있습니다.

- build command: `pip install -r requirements.txt`
- start command: `python main.py`

## 디렉터리 구조

```text
api/         Flask 라우트와 API 서버
engine/      데이터 수집, 지표 계산, 점수 계산, 스캐너, 포트폴리오 로직
static/      CSS/JS 정적 파일
templates/   HTML 템플릿
main.py      애플리케이션 실행 진입점
render.yaml  Render 배포 설정
requirements.txt  Python 의존성
```