"""
1. 종목 선별: (거래량>=100만 & 거래대금>=100억) 또는 상한가
"""
import pandas as pd
from pykrx import stock

from src.config_loader import load_config


def get_ticker_name(ticker: str) -> str:
    """Return stock name for ticker."""
    try:
        return stock.get_market_ticker_name(ticker) or ticker
    except Exception:
        return ticker


def run_screener(target_date: str) -> pd.DataFrame:
    """
    Run screener for a single date (YYYYMMDD).
    Returns DataFrame with columns: ticker, name, volume, trading_value, close, change_pct, etc.
    """
    cfg = load_config()
    min_vol = cfg["screener"]["min_volume"]
    min_val = cfg["screener"]["min_trading_value"]
    include_limit_up = cfg["screener"].get("include_limit_up", False)
    limit_up_pct = cfg["screener"].get("limit_up_change_pct", 29.5)

    # Single-date all-stock OHLCV (index = ticker)
    try:
        df = stock.get_market_ohlcv_by_ticker(target_date, market="ALL")
    except Exception as e:
        raise RuntimeError(f"pykrx 조회 실패 (날짜={target_date}): {e}") from e

    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "ticker", "name", "volume", "trading_value", "close",
                "change_pct", "open", "high", "low"
            ]
        )

    # Column names from pykrx (Korean): 시가, 고가, 저가, 종가, 거래량, 거래대금, 등락률
    # Handle both possible column naming (KRX may return different names in some versions)
    col_map = {
        "시가": "open", "고가": "high", "저가": "low", "종가": "close",
        "거래량": "volume", "거래대금": "trading_value", "등락률": "change_pct",
    }
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    if rename:
        df = df.rename(columns=rename)
    # If already English or different names, ensure we have volume and trading_value
    if "거래량" in df.columns and "volume" not in df.columns:
        df = df.rename(columns={"거래량": "volume"})
    if "거래대금" in df.columns and "trading_value" not in df.columns:
        df = df.rename(columns={"거래대금": "trading_value"})
    if "등락률" in df.columns and "change_pct" not in df.columns:
        df = df.rename(columns={"등락률": "change_pct"})
    if "종가" in df.columns and "close" not in df.columns:
        df = df.rename(columns={"종가": "close"})

    df = df.reset_index()
    # First column after reset_index is ticker (pykrx index name may be "티커")
    first_col = df.columns[0]
    if first_col != "ticker":
        df = df.rename(columns={first_col: "ticker"})

    # Ensure numeric
    for col in ("volume", "trading_value", "close", "change_pct"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Filter: (거래량·거래대금 조건) OR (상한가)
    if "volume" not in df.columns or "trading_value" not in df.columns:
        return pd.DataFrame(
            columns=[
                "ticker", "name", "volume", "trading_value", "close",
                "change_pct", "open", "high", "low"
            ]
        )
    condition_vol_val = (df["volume"] >= min_vol) & (df["trading_value"] >= min_val)
    condition_limit_up = (df["change_pct"] >= limit_up_pct) if include_limit_up else pd.Series(False, index=df.index)
    filtered = df[condition_vol_val | condition_limit_up].copy()
    filtered["ticker"] = filtered["ticker"].astype(str).str.zfill(6)
    filtered["name"] = filtered["ticker"].map(get_ticker_name)
    # Reorder columns
    out_cols = ["ticker", "name", "volume", "trading_value", "close", "change_pct"]
    for c in ("open", "high", "low"):
        if c in filtered.columns:
            out_cols.append(c)
    filtered = filtered[[c for c in out_cols if c in filtered.columns]]
    return filtered.sort_values("trading_value", ascending=False).reset_index(drop=True)
