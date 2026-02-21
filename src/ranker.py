"""
5. A~F 랭킹: 거래대금/뉴스/테마/밸류 점수 가중 합산 후 6등급
"""
import pandas as pd

from src.config_loader import load_config


def _normalize_series(s: pd.Series, min_val: float | None = None, max_val: float | None = None) -> pd.Series:
    """Scale to 0~100. If all same or single value, return 50."""
    if s is None or s.empty:
        return s
    s = pd.to_numeric(s, errors="coerce").fillna(0)
    if min_val is not None:
        s = s.clip(lower=min_val)
    if max_val is not None:
        s = s.clip(upper=max_val)
    lo, hi = s.min(), s.max()
    if hi <= lo:
        return pd.Series(50.0, index=s.index)
    return (s - lo) / (hi - lo) * 100


def score_to_grade(score: float) -> str:
    """Map 0~100 score to A~F. A: 83.33~100, B: 66.67~83.33, C: 50~66.67, D: 33.33~50, E: 16.67~33.33, F: 0~16.67."""
    if score >= 100 * 5 / 6:
        return "A"
    if score >= 100 * 4 / 6:
        return "B"
    if score >= 100 * 3 / 6:
        return "C"
    if score >= 100 * 2 / 6:
        return "D"
    if score >= 100 * 1 / 6:
        return "E"
    return "F"


def run_ranker(
    screened_df: pd.DataFrame,
    news_count: pd.Series,
    ticker_to_sector: pd.Series,
    sector_rank: dict[str, int],
    valuation_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    screened_df: ticker, name, volume, trading_value, change_pct, ...
    news_count: ticker -> count of news
    ticker_to_sector: ticker -> sector name
    sector_rank: sector name -> rank (1 = top theme)
    valuation_df: ticker, valuation_label (저평가/적정/고평가)
    Returns DataFrame with ticker, name, score_total, grade, score_trading, score_news, score_theme, score_valuation, ...
    """
    cfg = load_config()
    w = cfg.get("ranker", {})
    w_trading = w.get("weight_trading", 0.25)
    w_news = w.get("weight_news", 0.30)
    w_theme = w.get("weight_theme", 0.30)
    w_valuation = w.get("weight_valuation", 0.15)
    theme_top_bonus = w.get("theme_top_bonus", 0)

    df = screened_df[["ticker", "name", "volume", "trading_value"]].copy()
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    if "change_pct" in screened_df.columns:
        df["change_pct"] = screened_df["change_pct"].values

    # Trading score: higher trading_value + volume -> higher score
    df["score_trading"] = _normalize_series(
        df["trading_value"].fillna(0) / 1e9 + df["volume"].fillna(0) / 1e6
    )

    # News score
    df["news_count"] = df["ticker"].map(news_count).fillna(0)
    df["score_news"] = _normalize_series(df["news_count"])

    # Theme score: rank 1 (top theme) -> 100, higher rank -> lower score
    df["sector"] = df["ticker"].map(ticker_to_sector)
    max_rank = max(sector_rank.values()) if sector_rank else 1
    df["theme_rank"] = df["sector"].map(sector_rank).fillna(max_rank + 1).astype(int)
    # rank 1 -> 100, rank max_rank -> 0
    df["score_theme"] = 100 - (df["theme_rank"] - 1).clip(0) / max(1, max_rank) * 100
    # 1~3위 주도 테마 소속 종목 가산
    if theme_top_bonus > 0:
        bonus = (df["theme_rank"] <= 3).astype(int) * theme_top_bonus
        df["score_theme"] = (df["score_theme"] + bonus).clip(upper=100)

    # Valuation score: 저평가=high, 적정=mid, 고평가=low
    val_map = {"저평가": 100, "적정": 50, "고평가": 0, "N/A": 50}
    if valuation_df is not None and not valuation_df.empty:
        val_label = valuation_df.set_index("ticker")["valuation_label"]
        df["score_valuation"] = df["ticker"].map(val_label).map(val_map).fillna(50)
    else:
        df["score_valuation"] = 50.0

    df["score_total"] = (
        df["score_trading"] * w_trading
        + df["score_news"] * w_news
        + df["score_theme"] * w_theme
        + df["score_valuation"] * w_valuation
    )
    df["grade"] = df["score_total"].map(score_to_grade)
    return df.sort_values("score_total", ascending=False).reset_index(drop=True)
