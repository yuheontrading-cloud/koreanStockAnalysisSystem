#!/usr/bin/env python3
"""
한국 주식 분석·추천 프로그램 CLI 진입점.
사용법: python main.py [--date YYYY-MM-DD]
--date 생략 시 최근 영업일(또는 어제) 사용.
"""
import argparse
from datetime import datetime, timedelta

from src.pipeline import run_pipeline


def get_recent_business_day(dt: datetime) -> str:
    """Return YYYYMMDD for the most recent weekday (skip weekend)."""
    while dt.weekday() >= 5:  # 5=Saturday, 6=Sunday
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


def parse_args():
    parser = argparse.ArgumentParser(description="한국 주식 분석·추천 (거래량/거래대금 선별 → 뉴스·테마·밸류 → A~F 랭크)")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="대상 일자 (YYYY-MM-DD 또는 YYYYMMDD). 생략 시 어제(또는 최근 영업일)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="파일 저장 없이 콘솔만 출력",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.date:
        raw = args.date.replace("-", "")
        if len(raw) != 8:
            raise SystemExit("--date는 YYYY-MM-DD 또는 YYYYMMDD 형식이어야 합니다.")
        target_date = raw
    else:
        yesterday = datetime.now() - timedelta(days=1)
        target_date = get_recent_business_day(yesterday)

    run_pipeline(target_date=target_date, save_output=not args.no_save)


if __name__ == "__main__":
    main()
