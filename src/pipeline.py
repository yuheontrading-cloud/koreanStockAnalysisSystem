"""
Pipeline: Screener -> News -> Theme -> Valuation -> Ranker -> Report
"""
from pathlib import Path

from src import news_collector, ranker, report, screener, theme_analyzer, valuation
from src.config_loader import load_config


def run_pipeline(target_date: str, save_output: bool = True):
    """
    target_date: YYYYMMDD
    save_output: if True, write CSV/HTML to output/{date}/
    """
    cfg = load_config()
    out_cfg = cfg.get("output", {})
    save_csv = save_output and out_cfg.get("save_csv", True)
    save_html = save_output and out_cfg.get("save_html", True)
    save_excel = save_output and out_cfg.get("save_excel", False)

    # 1. Screener
    screened = screener.run_screener(target_date)
    if screened.empty:
        print(f"[{target_date}] 조건 충족 종목 없음.")
        return

    # 2. Theme (need sector for valuation and ranker)
    themes_df, ticker_to_sector = theme_analyzer.run_theme_analyzer(screened, target_date=target_date)
    sector_rank = {}
    for i, sec in enumerate(themes_df["sector"].tolist(), start=1):
        sector_rank[sec] = i

    # 2b. 1위 주도 테마만 사용 옵션: screened를 1위 테마 소속 종목만으로 제한
    only_top1 = cfg.get("theme", {}).get("only_top1_theme", False)
    if only_top1 and not themes_df.empty and not ticker_to_sector.empty:
        top_sector = themes_df["sector"].iloc[0]
        top1_tickers = ticker_to_sector[ticker_to_sector == top_sector].index.tolist()
        screened = screened[screened["ticker"].astype(str).str.zfill(6).isin(top1_tickers)].copy()
        if screened.empty:
            print(f"[{target_date}] 1위 주도 테마({top_sector}) 소속 종목 없음.")
            return

    # 3. Valuation (with sector for relative PER/PBR)
    valuation_df = valuation.run_valuation(
        screened["ticker"].astype(str).str.zfill(6).tolist(),
        target_date,
        sector_series=ticker_to_sector,
    )

    # 4. News
    news_df = news_collector.run_news_collector(screened, target_date)
    news_count = news_collector.news_count_by_ticker(news_df)

    # 5. Ranker
    ranked_df = ranker.run_ranker(
        screened,
        news_count,
        ticker_to_sector,
        sector_rank,
        valuation_df,
    )

    # 5b. 추천 종목 (랭크 기반)
    recommended_df = None
    if not ranked_df.empty and "grade" in ranked_df.columns:
        rec_cfg = cfg.get("recommend", {})
        min_grade = rec_cfg.get("min_grade", "B")
        max_count = rec_cfg.get("max_count", 20)
        grade_order = ["A", "B", "C", "D", "E", "F"]
        try:
            min_idx = grade_order.index(min_grade)
            allowed = set(grade_order[: min_idx + 1])
        except ValueError:
            allowed = {"A", "B"}
        recommended_df = (
            ranked_df[ranked_df["grade"].isin(allowed)]
            .sort_values("score_total", ascending=False)
            .head(max_count)
        )

    # 6. Report
    report.print_console(
        target_date=target_date,
        screened=screened,
        themes_df=themes_df,
        valuation_df=valuation_df,
        news_df=news_df,
        ranked_df=ranked_df,
    )

    if save_output:
        out_dir = Path(__file__).resolve().parent.parent / "output" / target_date
        out_dir.mkdir(parents=True, exist_ok=True)
        if save_csv:
            report.save_csv(out_dir, screened, themes_df, valuation_df, news_df, ranked_df, recommended_df=recommended_df)
        if save_html:
            report.save_html(
                out_dir,
                target_date=target_date,
                screened=screened,
                themes_df=themes_df,
                valuation_df=valuation_df,
                news_df=news_df,
                ranked_df=ranked_df,
                recommended_df=recommended_df,
            )
        if save_excel:
            report.save_excel(out_dir, screened, themes_df, valuation_df, news_df, ranked_df)

