import feedparser, requests
from bs4 import BeautifulSoup
from .utils import logger, retry_net
from .config import NEWS_RSS

# リトライ付きのRSSフェッチ
@retry_net
def fetch_rss(max_items: int = 8):
    feed = feedparser.parse(NEWS_RSS)
    items = []
    for e in feed.entries[:max_items]:
        items.append({"title": e.title, "link": getattr(e, "link", None)})
    logger.info(f"Fetched {len(items)} RSS items")
    return items

# リトライ付きの記事テキストフェッチ
@retry_net
def fetch_article_text(url: str) -> str:
    try:
        html = requests.get(url, timeout=10).text
        soup = BeautifulSoup(html, "lxml")
        # シンプル抽出（必要ならxpath/ルールを増やす）
        for s in soup(["script","style","noscript"]):
            s.decompose()
        text = "\n".join(t.strip() for t in soup.get_text("\n").splitlines() if t.strip())
        return text[:8000]  # トークン抑制
    except Exception:
        return ""