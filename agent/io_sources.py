import feedparser, requests
from bs4 import BeautifulSoup
from .utils import logger, retry_net
from .config import NEWS_FEEDS
from datetime import datetime, timezone
from urllib.parse import urlparse


def _to_dt(entry):
    tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tm:
        return datetime(*tm[:6], tzinfo=timezone.utc)
    return None


@retry_net
def fetch_rss_feed(url: str, max_items: int = 10):
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:max_items]:
        items.append({
            "title": getattr(e, "title", ""),
            "link": getattr(e, "link", None),
            "summary": getattr(e, "summary", ""),
            "published": _to_dt(e),
            "source": urlparse(url).netloc,
        })
    logger.info(f"Fetched {len(items)} items from {url}")
    return items


def fetch_all_rss(max_items_per_feed: int = 10, limit: int = 100):
    all_items = []
    for url in NEWS_FEEDS:
        try:
            all_items.extend(fetch_rss_feed(url, max_items=max_items_per_feed))
        except Exception as e:
            logger.warning(f"RSS fetch failed for {url}: {e}")
    # 新しい順に
    all_items.sort(key=lambda x: x.get("published") or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
    # 上限
    return all_items[:limit]


@retry_net
def fetch_article_text(url: str) -> str:
    try:
        html = requests.get(url, timeout=10).text
        soup = BeautifulSoup(html, "lxml")
        # シンプル抽出（必要ならルールを増やす）
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        text = "".join(t.strip() for t in soup.get_text("").splitlines() if t.strip())
        return text[:8000]  # トークン抑制
    except Exception:
        return ""
