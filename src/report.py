"""
콘솔 및 파일 출력 (CSV, HTML, Excel)
"""
import html as html_lib
from pathlib import Path

import pandas as pd


def _df_to_html_with_change_color(df: pd.DataFrame, change_pct_columns: list[str] | None = None) -> str:
    """DataFrame to HTML table; cells in change_pct_columns get class 'up' or 'down' by value."""
    if df.empty:
        return "<p>데이터 없음</p>"
    change_cols = change_pct_columns or []
    if "change_pct" in df.columns and "change_pct" not in change_cols:
        change_cols.append("change_pct")

    def cell_class(col: str, val) -> str:
        if col not in change_cols:
            return ""
        try:
            v = float(val)
            if v > 0:
                return "up"
            if v < 0:
                return "down"
        except (TypeError, ValueError):
            pass
        return ""

    html = ["<table class='report-table'><thead><tr>"]
    for c in df.columns:
        html.append(f"<th>{html_lib.escape(str(c))}</th>")
    html.append("</tr></thead><tbody>")
    for _, row in df.iterrows():
        html.append("<tr>")
        for col in df.columns:
            val = row[col]
            cls = cell_class(col, val)
            esc = html_lib.escape(str(val) if pd.notna(val) else "")
            if cls:
                html.append(f"<td class='{cls}'>{esc}</td>")
            else:
                html.append(f"<td>{esc}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    return "\n".join(html)


def print_console(
    target_date: str,
    screened: pd.DataFrame,
    themes_df: pd.DataFrame,
    valuation_df: pd.DataFrame,
    news_df: pd.DataFrame,
    ranked_df: pd.DataFrame,
) -> None:
    print(f"\n=== 한국 주식 분석 결과 ({target_date}) ===\n")
    print(f"[선별 종목] 거래량 100만·거래대금 100억 이상 또는 상한가: {len(screened)}건\n")
    if not ranked_df.empty:
        print("--- A~F 랭크 (상위 20) ---")
        cols = ["ticker", "name", "grade", "score_total", "score_trading", "score_news", "score_theme", "score_valuation"]
        cols = [c for c in cols if c in ranked_df.columns]
        print(ranked_df.head(20)[cols].to_string(index=False))
    print("\n--- 주도 테마 (상위 10) ---")
    print(themes_df.head(10).to_string(index=False))
    if not valuation_df.empty:
        print("\n--- 밸류에이션 요약 (저평가 종목) ---")
        low = valuation_df[valuation_df["valuation_label"] == "저평가"]
        print(low[["ticker", "per", "pbr", "valuation_label"]].head(15).to_string(index=False))
    print("\n--- 뉴스 수 (종목별) ---")
    if not news_df.empty:
        nc = news_df.groupby("ticker").size().sort_values(ascending=False).head(10)
        print(nc.to_string())
    print()


def save_csv(
    out_dir: Path,
    screened: pd.DataFrame,
    themes_df: pd.DataFrame,
    valuation_df: pd.DataFrame,
    news_df: pd.DataFrame,
    ranked_df: pd.DataFrame,
) -> None:
    screened.to_csv(out_dir / "screened.csv", index=False, encoding="utf-8-sig")
    themes_df.to_csv(out_dir / "themes.csv", index=False, encoding="utf-8-sig")
    valuation_df.to_csv(out_dir / "valuation.csv", index=False, encoding="utf-8-sig")
    news_df.to_csv(out_dir / "news.csv", index=False, encoding="utf-8-sig")
    ranked_df.to_csv(out_dir / "ranked.csv", index=False, encoding="utf-8-sig")
    print(f"CSV 저장: {out_dir}")


def save_html(
    out_dir: Path,
    target_date: str,
    screened: pd.DataFrame,
    themes_df: pd.DataFrame,
    valuation_df: pd.DataFrame,
    news_df: pd.DataFrame,
    ranked_df: pd.DataFrame,
) -> None:
    html = []
    html.append("<!DOCTYPE html><html><head><meta charset='utf-8'><title>한국 주식 분석 " + target_date + "</title>")
    html.append("<style>")
    html.append("body{font-family:Malgun Gothic,sans-serif;margin:20px;background:#fafafa}")
    html.append(".cards{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}")
    html.append(".card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:14px 20px;min-width:140px}")
    html.append(".card strong{display:block;font-size:1.4em;color:#333}")
    html.append(".report-table{width:100%;max-width:100%;border-collapse:collapse;margin:10px 0;background:#fff;overflow-x:auto}")
    html.append(".report-table th,.report-table td{border:1px solid #ccc;padding:6px 10px;text-align:left}")
    html.append(".report-table th{background:#eee}")
    html.append(".up{color:#c62828;background-color:#ffebee}")
    html.append(".down{color:#1565c0;background-color:#e3f2fd}")
    html.append("h1{color:#333} h2{margin-top:24px;color:#444} h3{margin-top:16px;color:#555}")
    html.append(".section{margin:20px 0}")
    html.append(".news-block{background:#fff;border:1px solid #ddd;border-radius:6px;padding:12px;margin:10px 0}")
    html.append(".news-block h4{margin:0 0 8px 0;color:#1976d2}")
    html.append(".news-item{margin:8px 0;padding:6px 0;border-bottom:1px solid #eee}")
    html.append(".news-item:last-child{border-bottom:none}")
    html.append(".scroll-wrap{max-height:400px;overflow-y:auto}")
    html.append("</style></head><body>")

    html.append(f"<h1>한국 주식 분석 결과 ({target_date})</h1>")

    # Summary cards
    n_screened = len(screened)
    n_themes = len(themes_df)
    n_news = len(news_df)
    n_a = len(ranked_df[ranked_df["grade"] == "A"]) if not ranked_df.empty and "grade" in ranked_df.columns else 0
    html.append("<div class='cards'>")
    html.append(f"<div class='card'>선별 종목 <strong>{n_screened}</strong>건</div>")
    html.append(f"<div class='card'>주도 테마 <strong>{n_themes}</strong>개</div>")
    html.append(f"<div class='card'>뉴스 <strong>{n_news}</strong>건</div>")
    html.append(f"<div class='card'>A등급 <strong>{n_a}</strong>건</div>")
    html.append("</div>")

    # A~F 랭크 (with change_pct color)
    html.append("<div class='section'><h2>A~F 랭크</h2>")
    rank_display = ranked_df.copy()
    if "change_pct" not in rank_display.columns and "change_pct" in screened.columns and not screened.empty:
        ch = screened.set_index("ticker")["change_pct"]
        rank_display["change_pct"] = rank_display["ticker"].map(ch)
    html.append(_df_to_html_with_change_color(rank_display.head(50), change_pct_columns=["change_pct"]))
    html.append("</div>")

    # 주도 테마 + 차트
    html.append("<div class='section'><h2>주도 테마</h2>")
    html.append(_df_to_html_with_change_color(themes_df))
    if not themes_df.empty and "theme_strength" in themes_df.columns:
        labels = themes_df["sector"].tolist()
        values = themes_df["theme_strength"].tolist()
        html.append("<div style='max-width:600px;height:280px;margin:16px 0'><canvas id='themeChart'></canvas></div>")
        html.append("<script src='https://cdn.jsdelivr.net/npm/chart.js'></script>")
        html.append("<script>")
        html.append("new Chart(document.getElementById('themeChart'),{type:'bar',data:{labels:" + str(labels) + ",datasets:[{label:'테마 강도(상승률 합)',data:" + str(values) + ",backgroundColor:'rgba(25,118,210,0.6)'}]},options:{indexAxis:'y',responsive:true,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true}}});")
        html.append("</script>")
    html.append("</div>")

    # 밸류에이션
    html.append("<div class='section'><h2>밸류에이션 (PER/PBR)</h2>")
    html.append(valuation_df.to_html(index=False, classes="report-table"))
    html.append("</div>")

    # 선별 종목 (상승/하락 색상)
    html.append("<div class='section'><h2>선별 종목</h2>")
    html.append(_df_to_html_with_change_color(screened))
    html.append("</div>")

    # 종목별 뉴스 (전체, 요약 포함). 뉴스 0건이어도 선별 종목별 블록 표시
    html.append("<div class='section'><h2>종목별 뉴스</h2>")
    if news_df.empty:
        for _, row in screened.iterrows():
            ticker = str(row.get("ticker", "")).zfill(6)
            name = row.get("name", ticker)
            html.append(f"<div class='news-block'><h4>{html_lib.escape(str(name))} ({ticker})</h4>")
            html.append("<p class='news-item'>해당 종목의 뉴스가 수집되지 않았습니다. (선택일자 필터 사용 시 해당일 뉴스만 표시됩니다.)</p>")
            html.append("</div>")
    else:
        has_summary = "news_body_summary" in news_df.columns
        for ticker, grp in news_df.groupby("ticker"):
            name = grp["name"].iloc[0] if "name" in grp.columns else ticker
            if pd.isna(name):
                name = ticker
            html.append(f"<div class='news-block'><h4>{html_lib.escape(str(name))} ({ticker})</h4>")
            for _, r in grp.iterrows():
                title = r.get("news_title", "") or ""
                link = r.get("news_link", "") or ""
                date = r.get("news_date", "") or ""
                summary = (r.get("news_body_summary") or r.get("news_summary") or "") if has_summary else (r.get("news_summary") or "")
                if pd.isna(summary):
                    summary = ""
                html.append("<div class='news-item'>")
                if link:
                    html.append(f"<a href='{html_lib.escape(str(link))}' target='_blank' rel='noopener'>" + html_lib.escape(str(title)[:200]) + "</a>")
                else:
                    html.append(html_lib.escape(str(title)[:200]))
                if date:
                    html.append(f" <span style='color:#666'> {html_lib.escape(str(date))}</span>")
                if summary:
                    html.append(f"<div style='font-size:0.9em;color:#555;margin-top:4px'>{html_lib.escape(str(summary)[:500])}</div>")
                html.append("</div>")
            html.append("</div>")
    html.append("</div>")

    # 전체 뉴스 테이블 (스크롤)
    html.append("<div class='section'><h2>뉴스 전체</h2>")
    if news_df.empty:
        html.append("<p>수집된 뉴스가 없습니다. config에서 filter_by_target_date를 false로 하거나 target_date_tolerance_days를 늘려 보세요.</p>")
    else:
        html.append("<div class='scroll-wrap'>")
        html.append(news_df.to_html(index=False, classes="report-table"))
        html.append("</div>")
    html.append("</div>")

    html.append("</body></html>")
    (out_dir / "report.html").write_text("\n".join(html), encoding="utf-8")
    print(f"HTML 저장: {out_dir / 'report.html'}")


def save_excel(
    out_dir: Path,
    screened: pd.DataFrame,
    themes_df: pd.DataFrame,
    valuation_df: pd.DataFrame,
    news_df: pd.DataFrame,
    ranked_df: pd.DataFrame,
) -> None:
    path = out_dir / "report.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        ranked_df.to_excel(w, sheet_name="Ranked", index=False)
        themes_df.to_excel(w, sheet_name="Themes", index=False)
        valuation_df.to_excel(w, sheet_name="Valuation", index=False)
        screened.to_excel(w, sheet_name="Screened", index=False)
        news_df.to_excel(w, sheet_name="News", index=False)
    print(f"Excel 저장: {path}")
