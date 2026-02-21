"""
3. 주도 테마 분석: 선별 종목의 업종(Sector) 집계 및 상위 N개 주도 테마
"""
import pandas as pd
from pykrx import stock

from src.config_loader import load_config


def get_sector_mapping(date: str) -> pd.DataFrame:
    """Return DataFrame with columns: ticker (index), sector (업종명). Uses pykrx sector classifications."""
    out = []
    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = stock.get_market_sector_classifications(date, market)
            if df is not None and not df.empty:
                df = df.reset_index()
                # columns: 종목코드, 종목명, 업종명, ...
                code_col = df.columns[0]
                sector_col = "업종명" if "업종명" in df.columns else df.columns[2]
                df = df[[code_col, sector_col]].copy()
                df = df.rename(columns={code_col: "ticker", sector_col: "sector"})
                df["ticker"] = df["ticker"].astype(str).str.zfill(6)
                out.append(df)
        except Exception:
            continue
    if not out:
        return pd.DataFrame(columns=["ticker", "sector"])
    return pd.concat(out, ignore_index=True).drop_duplicates(subset=["ticker"], keep="first")


def run_theme_analyzer(
    screened_df: pd.DataFrame,
    target_date: str | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    screened_df: output of screener (columns include ticker, name, ...).
    target_date: YYYYMMDD for sector lookup (required for pykrx).
    Returns:
      - themes_df: top N sectors with count and sample tickers (columns: sector, count, sample_tickers)
      - ticker_to_sector: Series ticker -> sector name for screened stocks
    """
    cfg = load_config()
    top_n = cfg.get("theme", {}).get("top_n_sectors", 10)

    if not target_date:
        return (
            pd.DataFrame(columns=["sector", "count", "sample_tickers"]),
            pd.Series(dtype=object),
        )
    krx = get_sector_mapping(target_date)
    if krx.empty or "sector" not in krx.columns:
        return (
            pd.DataFrame(columns=["sector", "count", "sample_tickers"]),
            pd.Series(dtype=object),
        )

    tickers = screened_df["ticker"].astype(str).str.zfill(6)
    sub = krx[krx["ticker"].isin(tickers)][["ticker", "sector"]].copy()
    sub["sector"] = sub["sector"].fillna("(미분류)")

    # Merge change_pct from screened_df for theme strength
    if "change_pct" in screened_df.columns:
        change_ser = screened_df.set_index(screened_df["ticker"].astype(str).str.zfill(6))["change_pct"]
        sub["change_pct"] = sub["ticker"].map(change_ser)
    else:
        sub["change_pct"] = 0.0
    sub["change_pct"] = pd.to_numeric(sub["change_pct"], errors="coerce").fillna(0)

    weight_by_rise = cfg.get("theme", {}).get("weight_by_change_pct", True)
    if weight_by_rise:
        # theme_strength = sum of positive change_pct (상승만 반영) per sector
        sub["rise"] = sub["change_pct"].clip(lower=0)
        agg_df = sub.groupby("sector", as_index=False).agg(
            count=("ticker", "count"),
            theme_strength=("rise", "sum"),
        )
        agg_df = agg_df.sort_values("theme_strength", ascending=False).head(top_n)
    else:
        agg_df = sub.groupby("sector", as_index=False).agg(count=("ticker", "count"))
        agg_df["theme_strength"] = agg_df["count"]
        agg_df = agg_df.sort_values("count", ascending=False).head(top_n)

    sample = sub.groupby("sector")["ticker"].apply(lambda x: ", ".join(x.head(2).tolist())).to_dict()
    agg_df["sample_tickers"] = agg_df["sector"].map(sample)
    themes_df = agg_df

    ticker_to_sector = sub.set_index("ticker")["sector"]
    return themes_df, ticker_to_sector


def get_ticker_sector_series(screened_df: pd.DataFrame) -> pd.Series:
    """Convenience: return only ticker -> sector for screened stocks."""
    _, ser = run_theme_analyzer(screened_df)
    return ser
