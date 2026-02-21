"""
4. 밸류에이션: PER, PBR 조회 및 업종 대비 저평가/고평가 판정
"""
import pandas as pd
from pykrx import stock

from src.config_loader import load_config


def _ensure_english_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Korean columns to English if present."""
    if df is None or df.empty:
        return df
    col_map = {"BPS": "bps", "PER": "per", "PBR": "pbr", "EPS": "eps", "DIV": "div", "DPS": "dps"}
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    if rename:
        df = df.rename(columns=rename)
    return df


def run_valuation(
    tickers: list[str],
    target_date: str,
    sector_series: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Get PER/PBR for given tickers on target_date and judge undervalued/overvalued.
    sector_series: ticker -> sector name (from theme_analyzer). If provided, use sector median for comparison.
    Returns DataFrame with columns: ticker, per, pbr, valuation_label, sector_median_per, sector_median_pbr (if sector given).
    """
    cfg = load_config()
    val_cfg = cfg.get("valuation", {})
    under_per = val_cfg.get("undervalued_per_ratio", 0.8)
    over_per = val_cfg.get("overvalued_per_ratio", 1.2)
    under_pbr = val_cfg.get("undervalued_pbr_ratio", 0.8)
    over_pbr = val_cfg.get("overvalued_pbr_ratio", 1.2)

    # Get market-wide fundamental for the date (all tickers); then filter to our list
    try:
        fund = stock.get_market_fundamental_by_ticker(target_date, market="ALL")
    except Exception as e:
        raise RuntimeError(f"pykrx fundamental 조회 실패 (날짜={target_date}): {e}") from e

    if fund is None or fund.empty:
        return _empty_valuation_df()

    fund = _ensure_english_columns(fund.copy())
    fund = fund.reset_index()
    first_col = fund.columns[0]
    if first_col != "ticker":
        fund = fund.rename(columns={first_col: "ticker"})
    fund["ticker"] = fund["ticker"].astype(str).str.zfill(6)

    # Filter to requested tickers
    ticker_set = set(str(t).zfill(6) for t in tickers)
    fund = fund[fund["ticker"].isin(ticker_set)].copy()

    for col in ("per", "pbr", "PER", "PBR"):
        if col in fund.columns:
            fund[col] = pd.to_numeric(fund[col], errors="coerce")
    if "per" not in fund.columns and "PER" in fund.columns:
        fund["per"] = fund["PER"]
    if "pbr" not in fund.columns and "PBR" in fund.columns:
        fund["pbr"] = fund["PBR"]

    # Sector medians: if we have sector_series, get sector medians from full fundamental
    sector_median_per: dict[str, float] = {}
    sector_median_pbr: dict[str, float] = {}
    if sector_series is not None and not sector_series.empty:
        full = stock.get_market_fundamental_by_ticker(target_date, market="ALL")
        if full is not None and not full.empty:
            full = _ensure_english_columns(full.reset_index())
            tc = full.columns[0]
            if tc != "ticker":
                full = full.rename(columns={tc: "ticker"})
            full["ticker"] = full["ticker"].astype(str).str.zfill(6)
            full["sector"] = full["ticker"].map(sector_series)
            for c in ("per", "pbr", "PER", "PBR"):
                if c in full.columns:
                    full[c] = pd.to_numeric(full[c], errors="coerce")
            if "per" not in full.columns and "PER" in full.columns:
                full["per"] = full["PER"]
            if "pbr" not in full.columns and "PBR" in full.columns:
                full["pbr"] = full["PBR"]
            for sec in full["sector"].dropna().unique():
                sub = full[full["sector"] == sec]
                per_vals = sub.get("per", sub.get("PER")).dropna()
                pbr_vals = sub.get("pbr", sub.get("PBR")).dropna()
                per_vals = per_vals[per_vals > 0]
                pbr_vals = pbr_vals[pbr_vals > 0]
                sector_median_per[sec] = float(per_vals.median()) if len(per_vals) else float("nan")
                sector_median_pbr[sec] = float(pbr_vals.median()) if len(pbr_vals) else float("nan")

    # Valuation label: sector-relative or absolute
    def label_row(row):
        per = row.get("per", row.get("PER", float("nan")))
        pbr = row.get("pbr", row.get("PBR", float("nan")))
        sector = row.get("sector")
        if pd.isna(per) and pd.isna(pbr):
            return "N/A"
        if sector and sector in sector_median_per and sector in sector_median_pbr:
            med_per = sector_median_per[sector]
            med_pbr = sector_median_pbr[sector]
            per_ok = not pd.isna(med_per) and med_per > 0 and not pd.isna(per) and per > 0
            pbr_ok = not pd.isna(med_pbr) and med_pbr > 0 and not pd.isna(pbr) and pbr > 0
            if per_ok and per <= med_per * under_per and (not pbr_ok or pbr <= med_pbr * under_pbr):
                return "저평가"
            if per_ok and per >= med_per * over_per or (pbr_ok and pbr >= med_pbr * over_pbr):
                return "고평가"
            return "적정"
        # Absolute fallback
        if not pd.isna(per) and per > 0:
            if per <= 15:
                return "저평가"
            if per >= 30:
                return "고평가"
        if not pd.isna(pbr) and pbr > 0:
            if pbr <= 1.0:
                return "저평가"
            if pbr >= 3.0:
                return "고평가"
        return "적정"

    if sector_series is not None:
        fund["sector"] = fund["ticker"].map(sector_series)
    fund["valuation_label"] = fund.apply(label_row, axis=1)
    if sector_series is not None:
        fund["sector_median_per"] = fund["sector"].map(sector_median_per)
        fund["sector_median_pbr"] = fund["sector"].map(sector_median_pbr)
    return fund


def _empty_valuation_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ticker", "per", "pbr", "valuation_label",
            "sector", "sector_median_per", "sector_median_pbr",
        ]
    )
