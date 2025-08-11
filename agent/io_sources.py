# agent/io_sources.py
from __future__ import annotations

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from typing import List, Dict, Optional

from .utils import logger, retry_net
from .config import NEWS_FEEDS, NEWS_RSS, NEWS_MAX_AGE_DAYS


def _to_dt(entry) -> Optional[datetime]:
    """
    feedparserのエントリから日時を抽出（UTCのaware datetimeに）
    優先順: published_parsed -> updated_parsed
    """
    tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tm:
        # tmはtime.struct_time
        return datetime(*tm[:6], tzinfo=timezone.utc)
    return None


@retry_net
def fetch_rss_feed(url: str, max_items: int = 10) -> List[Dict]:
    """
    単一RSSフィードを取得し、必要な項目だけを抽出
    - title, link, summary, published(UTC datetime), source(domain)
    """
    feed = feedparser.parse(url)
    items: List[Dict] = []
    for e in feed.entries[:max_items]:
        items.append(
            {
                "title": getattr(e, "title", "") or "",
                "link": getattr(e, "link", None),
                "summary": getattr(e, "summary", "") or "",
                "published": _to_dt(e),
                "source": urlparse(url).netloc,
            }
        )
    logger.info(f"Fetched {len(items)} items from {url}")
    return items


def fetch_all_rss(max_items_per_feed: int = 10, limit: int = 100) -> List[Dict]:
    """
    複数RSSからまとめて取得 → 直近NEWS_MAX_AGE_DAYSでフィルタ → 新しい順に整列 → 上位limit件
    """
    all_items: List[Dict] = []
    for url in NEWS_FEEDS:
        try:
            all_items.extend(fetch_rss_feed(url, max_items=max_items_per_feed))
        except Exception as e:
            logger.warning(f"RSS fetch failed for {url}: {e}")

    # 発行日のフィルタ（既定: 直近 NEWS_MAX_AGE_DAYS 日）
    if NEWS_MAX_AGE_DAYS and NEWS_MAX_AGE_DAYS > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_MAX_AGE_DAYS)
        all_items = [
            it for it in all_items
            if it.get("published") and it["published"] >= cutoff
        ]

    # 新しい順にソート（発行日がないものは最古扱い）
    all_items.sort(
        key=lambda x: x.get("published") or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )
    return all_items[:limit]


@retry_net
def fetch_article_text(url: str) -> str:
    """
    記事本文の素朴スクレイピング（スニペット用途）
    - JS/CSS/ noscript を除去してテキスト化
    - 文字数は8,000文字で打ち切り（トークン節約）
    """
    try:
        html = requests.get(url, timeout=10).text
        soup = BeautifulSoup(html, "lxml")
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        text = "\n".join(t.strip() for t in soup.get_text("\n").splitlines() if t.strip())
        return text[:8000]
    except Exception:
        return ""


# ---- 互換ラッパー（旧 processors.run_summary 用） --------------------
@retry_net
def fetch_rss(max_items: int = 8) -> List[Dict]:
    """
    互換API: 旧実装のために最低限の {title, link} リストを返す
    - NEWS_FEEDS があれば先頭フィードだけ利用
    - なければ NEWS_RSS を利用
    """
    urls = NEWS_FEEDS or ([NEWS_RSS] if NEWS_RSS else [])
    if not urls:
        logger.warning("No RSS feed configured (NEWS_FEEDS/NEWS_RSS).")
        return []

    items = fetch_rss_feed(urls[0], max_items=max_items)
    return [{"title": it["title"], "link": it.get("link")} for it in items[:max_items]]
