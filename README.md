# 한국 주식 분석·추천 프로그램

거래량 500만주·거래대금 100억 원 이상 종목을 매일 선별하고, 뉴스·주도 테마·PER/PBR 밸류에이션을 반영해 **A~F 랭크**로 추천하는 Python 프로그램입니다.

**면책**: 본 프로그램은 참고용 스크리닝/랭킹 도구이며, 투자 추천이 아닙니다. 투자 책임은 전적으로 사용자에게 있습니다.

## 요구사항

- Python 3.10+
- Windows / macOS / Linux

## 설치

```bash
cd KoreanStockAnalysis
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

## 설정

1. **config/config.yaml**  
   선별 조건(거래량/거래대금), 뉴스(API/스크래핑), 테마 상위 N개, 밸류 비율, 랭킹 가중치, 출력 옵션 등을 수정할 수 있습니다.

2. **뉴스 수집**
   - **네이버 API 사용**: [네이버 개발자 센터](https://developers.naver.com)에서 애플리케이션 등록 후 Client ID/Secret 발급.  
     프로젝트 루트에 `.env` 파일을 만들고 다음 내용을 넣습니다.
     ```
     NAVER_CLIENT_ID=발급받은_ID
     NAVER_CLIENT_SECRET=발급받은_Secret
     ```
   - **API 미사용**: `config/config.yaml`에서 `news.use_api`를 `false`로 두면 네이버 금융 뉴스 스크래핑을 사용합니다. (요청 간격 준수)

## 실행

```bash
# 최근 영업일(어제) 기준 분석
python main.py

# 특정 일자 지정 (YYYY-MM-DD 또는 YYYYMMDD)
python main.py --date 2025-02-14

# 결과를 파일로 저장하지 않고 콘솔만 출력
python main.py --date 2025-02-14 --no-save
```

결과는 **output/YYYYMMDD/** 아래에 CSV·HTML(선택 시 Excel)로 저장됩니다.

## 처리 단계

1. **선별**: pykrx로 해당일 전종목 OHLCV 조회 후, 거래량 ≥ 500만주, 거래대금 ≥ 100억 원 필터
2. **테마**: pykrx 업종 분류로 선별 종목의 업종별 집계 → 주도 테마 상위 N개
3. **밸류에이션**: pykrx PER/PBR 조회, 업종 대비 저평가/적정/고평가 판정
4. **뉴스**: 종목별 최근 뉴스 수집 (네이버 API 또는 금융 뉴스 스크래핑)
5. **랭킹**: 거래·뉴스·테마·밸류 점수 가중 합산 후 A~F 등급 부여
6. **리포트**: 콘솔 요약 + CSV/HTML/Excel 저장

## 디렉터리 구조

```
KoreanStockAnalysis/
├── config/config.yaml   # 설정
├── src/
│   ├── screener.py      # 1. 종목 선별
│   ├── news_collector.py# 2. 뉴스 수집
│   ├── theme_analyzer.py# 3. 주도 테마
│   ├── valuation.py     # 4. PER/PBR 밸류
│   ├── ranker.py        # 5. A~F 랭크
│   ├── pipeline.py      # 파이프라인
│   └── report.py        # 출력
├── output/              # 일자별 결과
├── main.py
└── requirements.txt
```

## 라이선스 및 데이터 출처

- 주가·거래량·PER/PBR·업종: **pykrx** (KRX/네이버 스크래핑)
- 뉴스: 네이버 검색 API 또는 네이버 금융  
데이터 저작권은 각 제공처에 있으며, 참고용으로만 사용해야 합니다.
