"""
콘솔 및 파일 출력 (CSV, HTML, Excel)
"""
import re
import html as html_lib
from pathlib import Path

import pandas as pd

from src.config_loader import load_config


def _fmt_cell(val) -> str:
    """Format cell for display: float/number -> 2 decimal places, else str."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if isinstance(val, (int, float)):
        if isinstance(val, float):
            return f"{val:.2f}"
        return str(int(val))
    return str(val)


def strip_html_then_escape(s: str) -> str:
    """Replace <br> etc. with space, strip tags, then html.escape. Use for news title/summary/date."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s)
    # Replace br variants with space
    s = re.sub(r"<br\s*/?>|</br>|&lt;br\s*/?&gt;", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<b>|</b>|&amp;", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return html_lib.escape(s)


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
            esc = html_lib.escape(_fmt_cell(val) if pd.notna(val) else "")
            if cls:
                html.append(f"<td class='{cls}'>{esc}</td>")
            else:
                html.append(f"<td>{esc}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    return "\n".join(html)


def _news_df_to_html(news_df: pd.DataFrame) -> str:
    """News DataFrame to HTML with strip_html_then_escape on string columns so <br> etc. don't show as text."""
    if news_df.empty:
        return "<p>데이터 없음</p>"
    html = ["<table class='report-table'><thead><tr>"]
    for c in news_df.columns:
        html.append(f"<th>{html_lib.escape(str(c))}</th>")
    html.append("</tr></thead><tbody>")
    for _, row in news_df.iterrows():
        html.append("<tr>")
        for col in news_df.columns:
            val = row[col]
            if pd.isna(val):
                s = ""
            else:
                if isinstance(val, (int, float)):
                    s = html_lib.escape(_fmt_cell(val))
                else:
                    s = str(val)
                    if s.strip():
                        s = strip_html_then_escape(s)
                    else:
                        s = html_lib.escape(s)
            html.append(f"<td>{s}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    return "\n".join(html)


def _themes_table_to_html(df: pd.DataFrame, theme_top_n: int = 3) -> str:
    """Like _df_to_html_with_change_color but first theme_top_n rows get class theme-top."""
    if df.empty:
        return "<p>데이터 없음</p>"
    change_cols = ["change_pct"] if "change_pct" in df.columns else []

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
    for i, (_, row) in enumerate(df.iterrows()):
        row_cls = " class='theme-top'" if i < theme_top_n else ""
        html.append(f"<tr{row_cls}>")
        for col in df.columns:
            val = row[col]
            cls = cell_class(col, val)
            esc = html_lib.escape(_fmt_cell(val) if pd.notna(val) else "")
            if cls:
                html.append(f"<td class='{cls}'>{esc}</td>")
            else:
                html.append(f"<td>{esc}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    return "\n".join(html)


def _console_fmt_df(df: pd.DataFrame) -> pd.DataFrame:
    """Format float columns to 2 decimal places for console output."""
    if df.empty:
        return df
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    return out


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
        print(_console_fmt_df(ranked_df.head(20)[cols]).to_string(index=False))
    print("\n--- 주도 테마 (상위 10) ---")
    print(_console_fmt_df(themes_df.head(10)).to_string(index=False))
    if not valuation_df.empty:
        print("\n--- 밸류에이션 요약 (저평가 종목) ---")
        low = valuation_df[valuation_df["valuation_label"] == "저평가"]
        sub = low[["ticker", "per", "pbr", "valuation_label"]].head(15)
        print(_console_fmt_df(sub).to_string(index=False))
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
    recommended_df: pd.DataFrame | None = None,
) -> None:
    screened.to_csv(out_dir / "screened.csv", index=False, encoding="utf-8-sig")
    themes_df.to_csv(out_dir / "themes.csv", index=False, encoding="utf-8-sig")
    valuation_df.to_csv(out_dir / "valuation.csv", index=False, encoding="utf-8-sig")
    news_df.to_csv(out_dir / "news.csv", index=False, encoding="utf-8-sig")
    ranked_df.to_csv(out_dir / "ranked.csv", index=False, encoding="utf-8-sig")
    if recommended_df is not None and not recommended_df.empty:
        recommended_df.to_csv(out_dir / "recommended.csv", index=False, encoding="utf-8-sig")
    print(f"CSV 저장: {out_dir}")


def save_html(
    out_dir: Path,
    target_date: str,
    screened: pd.DataFrame,
    themes_df: pd.DataFrame,
    valuation_df: pd.DataFrame,
    news_df: pd.DataFrame,
    ranked_df: pd.DataFrame,
    recommended_df: pd.DataFrame | None = None,
) -> None:
    html = []
    html.append("<!DOCTYPE html><html><head><meta charset='utf-8'><title>한국 주식 분석 " + target_date + "</title>")
    html.append("<style>")
    html.append("body{font-family:Malgun Gothic,sans-serif;margin:20px;background:#f0f2f5;max-width:1200px;margin-left:auto;margin-right:auto}")
    html.append(".cards{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}")
    html.append(".card{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:14px 20px;min-width:140px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}")
    html.append(".card strong{display:block;font-size:1.4em;color:#333}")
    html.append(".report-table{width:100%;max-width:100%;border-collapse:collapse;margin:10px 0;background:#fff;overflow-x:auto;box-shadow:0 1px 3px rgba(0,0,0,0.06)}")
    html.append(".report-table th,.report-table td{border:1px solid #ddd;padding:8px 12px;text-align:left;font-size:0.95em}")
    html.append(".report-table th{background:#37474f;color:#fff;font-weight:bold}")
    html.append(".report-table tbody tr:nth-child(even){background:#f5f5f5}")
    html.append(".report-table tbody tr:nth-child(odd){background:#fff}")
    html.append(".up{color:#c62828;background-color:#ffebee}")
    html.append(".down{color:#1565c0;background-color:#e3f2fd}")
    html.append("h1{font-size:1.6em;color:#333;margin-bottom:8px} h2{font-size:1.3em;margin-top:28px;margin-bottom:12px;color:#444;padding-bottom:6px;border-bottom:1px solid #e0e0e0} h3{font-size:1.1em;margin-top:18px;color:#555}")
    html.append(".section{margin:24px 0;padding:16px;background:#fff;border-radius:8px;border:1px solid #e0e0e0;box-shadow:0 1px 3px rgba(0,0,0,0.06)}")
    html.append(".news-block{background:#fafafa;border:1px solid #e0e0e0;border-radius:6px;padding:12px;margin:10px 0;box-shadow:0 1px 2px rgba(0,0,0,0.04)}")
    html.append(".news-block h4{margin:0 0 8px 0;color:#1976d2}")
    html.append(".news-item{margin:8px 0;padding:6px 0;border-bottom:1px solid #eee}")
    html.append(".news-item:last-child{border-bottom:none}")
    html.append(".scroll-wrap{max-height:400px;overflow-y:auto}")
    html.append(".theme-top{font-size:1.05em;font-weight:bold;background:#e3f2fd !important;border-left:3px solid #1976d2}")
    html.append(".recommend-disclaimer{font-size:0.85em;color:#666;margin-top:8px;font-style:italic}")
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

    # 1) 추천 종목 (recommended_df or filter from ranked_df)
    rec_df = recommended_df
    if rec_df is None and not ranked_df.empty and "grade" in ranked_df.columns:
        cfg = load_config()
        rec_cfg = cfg.get("recommend", {})
        min_grade = rec_cfg.get("min_grade", "B")
        max_count = rec_cfg.get("max_count", 20)
        grade_order = ["A", "B", "C", "D", "E", "F"]
        try:
            min_idx = grade_order.index(min_grade)
            allowed = set(grade_order[: min_idx + 1])
        except ValueError:
            allowed = {"A", "B"}
        rec_df = ranked_df[ranked_df["grade"].isin(allowed)].sort_values("score_total", ascending=False).head(max_count)
    if rec_df is not None and not rec_df.empty:
        html.append("<div class='section'><h2>추천 종목</h2>")
        rec_display = rec_df.copy()
        if "change_pct" not in rec_display.columns and "change_pct" in screened.columns and not screened.empty:
            ch = screened.set_index("ticker")["change_pct"]
            rec_display["change_pct"] = rec_display["ticker"].map(ch)
        html.append(_df_to_html_with_change_color(rec_display, change_pct_columns=["change_pct"]))
        html.append("<p class='recommend-disclaimer'>참고용이며, 투자 책임은 본인에게 있습니다.</p>")
        html.append("</div>")

    # 2) 주도 테마 + 차트 (1~3위 .theme-top, 차트 상위 3개 다른 색)
    html.append("<div class='section'><h2>주도 테마</h2>")
    if not themes_df.empty:
        html.append(_themes_table_to_html(themes_df))
    if not themes_df.empty and "theme_strength" in themes_df.columns:
        labels = themes_df["sector"].tolist()
        values = [round(float(v), 2) for v in themes_df["theme_strength"].tolist()]
        n = len(values)
        colors = ["rgba(25,118,210,0.85)" if i < 3 else "rgba(25,118,210,0.5)" for i in range(n)]
        html.append("<div style='max-width:600px;height:280px;margin:16px 0'><canvas id='themeChart'></canvas></div>")
        html.append("<script src='https://cdn.jsdelivr.net/npm/chart.js'></script>")
        html.append("<script>")
        html.append("new Chart(document.getElementById('themeChart'),{type:'bar',data:{labels:" + str(labels) + ",datasets:[{label:'테마 강도(상승률 합)',data:" + str(values) + ",backgroundColor:" + str(colors) + "}]},options:{indexAxis:'y',responsive:true,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true}}});")
        html.append("</script>")
    html.append("</div>")

    # 3) A~F 랭크 (with change_pct color)
    html.append("<div class='section'><h2>A~F 랭크</h2>")
    rank_display = ranked_df.copy()
    if "change_pct" not in rank_display.columns and "change_pct" in screened.columns and not screened.empty:
        ch = screened.set_index("ticker")["change_pct"]
        rank_display["change_pct"] = rank_display["ticker"].map(ch)
    html.append(_df_to_html_with_change_color(rank_display.head(50), change_pct_columns=["change_pct"]))
    html.append("</div>")

    # 4) 선별 종목 (상승/하락 색상)
    html.append("<div class='section'><h2>선별 종목</h2>")
    html.append(_df_to_html_with_change_color(screened))
    html.append("</div>")

    # ---- 뉴스: 요약 → 종목별 → 전체 순 ----
    has_summary = not news_df.empty and ("news_body_summary" in news_df.columns or "news_summary" in news_df.columns)

    # 1) 뉴스 요약 (종목별 대표 1~2건: 제목+요약+링크+날짜)
    html.append("<div class='section'><h2>뉴스 요약</h2>")
    if news_df.empty:
        html.append("<p>수집된 뉴스가 없습니다.</p>")
        html.append("<p style='font-size:0.9em;color:#666'>선택한 날짜와 같은 날짜 뉴스만 표시됩니다. config에서 target_date_tolerance_days를 1로 하거나 parse_fail_keep을 true로 설정하면 더 많은 뉴스가 포함될 수 있습니다.</p>")
    else:
        for ticker, grp in news_df.groupby("ticker"):
            name = grp["name"].iloc[0] if "name" in grp.columns else ticker
            if pd.isna(name):
                name = ticker
            html.append(f"<div class='news-block'><h4>{strip_html_then_escape(str(name))} ({ticker})</h4>")
            shown = 0
            for _, r in grp.iterrows():
                if shown >= 2:
                    break
                summary = (r.get("news_body_summary") or r.get("news_summary") or "") if has_summary else (r.get("news_summary") or "")
                if pd.isna(summary):
                    summary = ""
                if not has_summary and not summary:
                    summary = "(요약 없음)"
                title = r.get("news_title", "") or ""
                link = r.get("news_link", "") or ""
                date = r.get("news_date", "") or ""
                html.append("<div class='news-item'>")
                if link:
                    html.append(f"<a href='{html_lib.escape(str(link))}' target='_blank' rel='noopener'>" + strip_html_then_escape(str(title)[:200]) + "</a>")
                else:
                    html.append(strip_html_then_escape(str(title)[:200]))
                if date:
                    html.append(f" <span style='color:#666'> {strip_html_then_escape(str(date))}</span>")
                html.append(f"<div style='font-size:0.9em;color:#555;margin-top:4px'>{strip_html_then_escape(str(summary)[:500])}</div>")
                html.append("</div>")
                shown += 1
            html.append("</div>")
    html.append("</div>")

    # 2) 종목별 뉴스 (전체)
    html.append("<div class='section'><h2>종목별 뉴스</h2>")
    if news_df.empty:
        for _, row in screened.iterrows():
            ticker = str(row.get("ticker", "")).zfill(6)
            name = row.get("name", ticker)
            html.append(f"<div class='news-block'><h4>{strip_html_then_escape(str(name))} ({ticker})</h4>")
            html.append("<p class='news-item'>해당 종목의 뉴스가 수집되지 않았습니다. (선택일자 필터 사용 시 해당일 뉴스만 표시됩니다.)</p>")
            html.append("</div>")
    else:
        for ticker, grp in news_df.groupby("ticker"):
            name = grp["name"].iloc[0] if "name" in grp.columns else ticker
            if pd.isna(name):
                name = ticker
            html.append(f"<div class='news-block'><h4>{strip_html_then_escape(str(name))} ({ticker})</h4>")
            for _, r in grp.iterrows():
                title = r.get("news_title", "") or ""
                link = r.get("news_link", "") or ""
                date = r.get("news_date", "") or ""
                summary = (r.get("news_body_summary") or r.get("news_summary") or "") if has_summary else (r.get("news_summary") or "")
                if pd.isna(summary):
                    summary = ""
                html.append("<div class='news-item'>")
                if link:
                    html.append(f"<a href='{html_lib.escape(str(link))}' target='_blank' rel='noopener'>" + strip_html_then_escape(str(title)[:200]) + "</a>")
                else:
                    html.append(strip_html_then_escape(str(title)[:200]))
                if date:
                    html.append(f" <span style='color:#666'> {strip_html_then_escape(str(date))}</span>")
                if summary:
                    html.append(f"<div style='font-size:0.9em;color:#555;margin-top:4px'>{strip_html_then_escape(str(summary)[:500])}</div>")
                html.append("</div>")
            html.append("</div>")
    html.append("</div>")

    # 3) 뉴스 전체 테이블 (스크롤, 셀 정규화)
    html.append("<div class='section'><h2>뉴스 전체</h2>")
    if news_df.empty:
        html.append("<p>수집된 뉴스가 없습니다. config에서 filter_by_target_date를 false로 하거나 target_date_tolerance_days를 늘려 보세요.</p>")
        html.append("<p style='font-size:0.9em;color:#666'>선택한 날짜와 같은 날짜 뉴스만 표시됩니다. config에서 target_date_tolerance_days를 1로 하거나 parse_fail_keep을 true로 설정하면 더 많은 뉴스가 포함될 수 있습니다.</p>")
    else:
        html.append("<div class='scroll-wrap'>")
        html.append(_news_df_to_html(news_df))
        html.append("</div>")
    html.append("</div>")

    # 5) 밸류에이션 (종목명 포함, 숫자 소수점 2자리)
    html.append("<div class='section'><h2>밸류에이션 (PER/PBR)</h2>")
    if not screened.empty and "ticker" in screened.columns and "name" in screened.columns and not valuation_df.empty:
        name_df = screened[["ticker", "name"]].drop_duplicates("ticker")
        name_df["ticker"] = name_df["ticker"].astype(str).str.zfill(6)
        val_copy = valuation_df.copy()
        val_copy["ticker"] = val_copy["ticker"].astype(str).str.zfill(6)
        val_display = val_copy.merge(name_df, on="ticker", how="left")
        rest = [c for c in val_display.columns if c not in ("ticker", "name")]
        val_display = val_display[["ticker", "name"] + rest]
        val_display["name"] = val_display["name"].fillna("")
        html.append(_df_to_html_with_change_color(val_display))
    else:
        html.append(_df_to_html_with_change_color(valuation_df))
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
