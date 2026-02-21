"""
2. 뉴스 수집: 선별 종목별 뉴스 - 네이버 API 또는 검색 결과 스크래핑, 본문 수집·요약
"""
import re
import time
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.config_loader import get_naver_credentials, load_config

_news_fallback_warned = False


def _parse_pubdate_to_yyyymmdd(pub_date: str) -> str | None:
    """Parse RFC 2822, ISO 8601, or similar to YYYYMMDD. Returns None if unparseable."""
    if not pub_date or not isinstance(pub_date, str):
        return None
    s = pub_date.strip()
    # RFC 2822: Mon, 26 Aug 2024 17:32:00 +0900
    strptime_fmts = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S",
        "%Y.%m.%d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
    ]
    for fmt in strptime_fmts:
        try:
            part = s[: min(len(s), 30)]
            dt = datetime.strptime(part, fmt.strip())
            return dt.strftime("%Y%m%d")
        except Exception:
            continue
    # ISO 8601: 2024-08-26T17:32:00+09:00 or 2024-08-26T17:32:00Z
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if iso:
        return iso.group(1) + iso.group(2) + iso.group(3)
    # YYYYMMDD or other numeric date
    m = re.search(r"(\d{4})[-./]?(\d{2})[-./]?(\d{2})", s)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    return None


def _days_diff_yyyymmdd(a: str, b: str) -> int:
    """Return (a - b) in days. a, b are YYYYMMDD."""
    if not a or not b or len(a) != 8 or len(b) != 8:
        return 999
    try:
        d1 = datetime.strptime(a, "%Y%m%d")
        d2 = datetime.strptime(b, "%Y%m%d")
        return (d1 - d2).days
    except Exception:
        return 999


def _fetch_article_body(url: str, timeout: int = 8) -> str:
    """Fetch news article URL and extract body text. Returns empty string on failure."""
    cfg = load_config()
    delay = cfg.get("news", {}).get("article_request_delay_seconds", 0.5)
    time.sleep(delay)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style"]):
            tag.decompose()
        # Common article body selectors (multiple sites)
        selectors = [
            "#news_body", ".news_body", "#articleBody", ".article_body", ".article-body",
            "div[itemprop='articleBody']", "article", ".article_view", "#articeBody",
            ".content_body", ".news_view", "#newsct_article", "main article",
        ]
        text_parts = []
        for sel in selectors:
            for el in soup.select(sel):
                t = el.get_text(separator=" ", strip=True)
                if t and len(t) > 100:
                    text_parts.append(t)
                    break
            if text_parts:
                break
        if not text_parts:
            # Fallback: first main or div with many p
            for main in soup.select("main, #main, .main, #content"):
                t = main.get_text(separator=" ", strip=True)
                if t and len(t) > 80:
                    text_parts.append(t)
                    break
        return " ".join(text_parts) if text_parts else ""
    except Exception:
        return ""


def _fetch_naver_api(query: str, display: int = 10, start: int = 1) -> list[dict]:
    """Naver search API news. Returns list of items with title, link, description, pubDate."""
    cred = get_naver_credentials()
    if not cred["client_id"] or not cred["client_secret"]:
        return []
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": cred["client_id"],
        "X-Naver-Client-Secret": cred["client_secret"],
    }
    params = {"query": query, "display": min(display, 100), "start": start, "sort": "date"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("items", [])
    except Exception:
        return []


def _fetch_naver_news_search_scrape(query: str, max_articles: int = 20) -> list[dict]:
    """Scrape Naver news search results. Returns list of {title, link, description, pubDate}.
    Note: Naver search often loads news via JavaScript, so this may return [] without browser automation.
    For reliable news, set NAVER_CLIENT_ID and NAVER_CLIENT_SECRET in .env (use_api=true)."""
    cfg = load_config()
    delay = cfg.get("news", {}).get("request_delay_seconds", 0.3)
    time.sleep(delay)
    url = "https://search.naver.com/search.naver?where=news&query=" + quote(query)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        rows = []
        seen_links = set()
        # 1) news_area > news_tit (최신 구조)
        for group in soup.select("div.news_area")[:max_articles * 2]:
            tit = group.select_one("a.news_tit")
            if not tit:
                tit = group.select_one("a[href*='news'], a[href*='article']")
            if not tit:
                continue
            link = tit.get("href", "").split("?")[0]
            if link in seen_links:
                continue
            seen_links.add(link)
            title = tit.get_text(strip=True)
            dsc = group.select_one("div.news_dsc, a.dsc_wrap, span.news_dsc, a.link_tit")
            summary = dsc.get_text(strip=True) if dsc else ""
            info = group.select_one("span.info, span.info_group")
            pub_date = info.get_text(strip=True) if info else ""
            rows.append({"title": title, "link": tit.get("href", ""), "description": summary, "pubDate": pub_date})
            if len(rows) >= max_articles:
                break
        # 2) a.news_tit 단독
        if len(rows) < max_articles:
            for a in soup.select("a.news_tit"):
                if len(rows) >= max_articles:
                    break
                href = a.get("href", "")
                if not href or href in seen_links:
                    continue
                seen_links.add(href)
                title = a.get_text(strip=True)
                if title and len(title) > 5:
                    rows.append({"title": title, "link": href, "description": "", "pubDate": ""})
        # 3) 뉴스 링크 패턴 (list_news, bx 등)
        if len(rows) < max_articles:
            for a in soup.select("ul.list_news a[href*='article'], div.bx a[href*='news'], div.bx a[href*='article']"):
                if len(rows) >= max_articles:
                    break
                href = a.get("href", "")
                if not href or href in seen_links:
                    continue
                title = a.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                seen_links.add(href)
                rows.append({"title": title, "link": href, "description": "", "pubDate": ""})
        return rows[:max_articles]
    except Exception:
        return []


def run_news_collector(
    screened_df: pd.DataFrame,
    target_date: str | None = None,
) -> pd.DataFrame:
    """
    screened_df: must have columns ticker, name.
    target_date: YYYYMMDD. When filter_by_target_date=true, only news on this date are kept.
    Returns DataFrame: ticker, name, news_title, news_link, news_summary, news_date, news_body_summary.
    """
    global _news_fallback_warned
    cfg = load_config()
    news_cfg = cfg.get("news", {})
    use_api = news_cfg.get("use_api", True)
    max_per = news_cfg.get("max_articles_per_stock", 20)
    filter_by_date = news_cfg.get("filter_by_target_date", True)
    tolerance_days = news_cfg.get("target_date_tolerance_days", 0)
    parse_fail_keep = news_cfg.get("parse_fail_keep", True)
    fetch_body = news_cfg.get("fetch_article_body", True)
    summary_max = news_cfg.get("summary_max_chars", 300)
    max_fetch_body = news_cfg.get("max_articles_fetch_body", 5)
    debug = news_cfg.get("debug", False)
    cred = get_naver_credentials()
    has_cred = bool(cred.get("client_id") and cred.get("client_secret"))

    rows = []
    _debug_total = 0
    _debug_parse_fail = 0
    _debug_filtered_date = 0
    for _, row in screened_df.iterrows():
        ticker = str(row["ticker"]).zfill(6)
        name = row.get("name", ticker)
        query = f"{name} 주가" if name else ticker
        items = []
        if use_api and has_cred:
            items = _fetch_naver_api(query, display=max_per)
        if not items:
            if use_api and has_cred is False and not _news_fallback_warned:
                print("[뉴스] API 키 없음. 검색 스크래핑으로 시도합니다.")
                _news_fallback_warned = True
            items = _fetch_naver_news_search_scrape(query, max_articles=max_per)
        for idx, it in enumerate(items):
            news_date = it.get("pubDate") or it.get("date") or ""
            if filter_by_date and target_date:
                _debug_total += 1
                parsed = _parse_pubdate_to_yyyymmdd(news_date)
                if parsed is None:
                    _debug_parse_fail += 1
                    if not parse_fail_keep:
                        continue
                else:
                    if tolerance_days == 0:
                        if parsed != target_date:
                            _debug_filtered_date += 1
                            continue
                    else:
                        diff = abs(_days_diff_yyyymmdd(parsed, target_date))
                        if diff > tolerance_days:
                            _debug_filtered_date += 1
                            continue
            body_summary = ""
            if fetch_body and idx < max_fetch_body:
                link = it.get("link") or it.get("news_link") or ""
                if link:
                    body = _fetch_article_body(link)
                    if body:
                        body_summary = body[:summary_max] + ("..." if len(body) > summary_max else "")
            if not body_summary:
                body_summary = (it.get("description") or it.get("summary") or "")[:summary_max]
            rows.append({
                "ticker": ticker,
                "name": name,
                "news_title": (it.get("title") or it.get("news_title") or "").replace("<b>", "").replace("</b>", ""),
                "news_link": it.get("link") or it.get("news_link") or "",
                "news_summary": it.get("description") or it.get("summary") or "",
                "news_date": news_date,
                "news_body_summary": body_summary or "(요약 없음)",
            })

    df = pd.DataFrame(rows)
    if debug and filter_by_date and target_date:
        print(f"[뉴스 디버그] 날짜 필터 대상 {_debug_total}건, 파싱 실패 {_debug_parse_fail}건, 날짜 불일치 제외 {_debug_filtered_date}건 → 수집 {len(rows)}건")
    if df.empty:
        df["news_body_summary"] = []
    elif "news_body_summary" not in df.columns:
        df["news_body_summary"] = ""
    return df


def news_count_by_ticker(news_df: pd.DataFrame) -> pd.Series:
    """Return series: ticker -> number of news articles (for ranker)."""
    if news_df is None or news_df.empty:
        return pd.Series(dtype=int)
    return news_df.groupby("ticker").size()
