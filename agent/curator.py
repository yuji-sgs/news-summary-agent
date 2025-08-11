import re
from datetime import datetime, timezone
from typing import List, Dict

from .io_sources import fetch_all_rss
from .llm import NewsItem, summarize_articles
from .config import PREF_PRIMARY, PREF_SECONDARY, NEWS_MAX_AGE_DAYS

def _norm(s: str) -> str:
    return (s or "").lower()

def _score_item(item: Dict, now=None) -> float:
    """
    キーワード＋新鮮度でスコアリング
    """
    text = _norm(f"{item.get('title','')} {item.get('summary','')}")
    score = 0.0
    for kw in PREF_PRIMARY:
        if kw and kw.lower() in text:
            score += 3.0
    for kw in PREF_SECONDARY:
        if kw and kw.lower() in text:
            score += 1.5
    if "agent" in text or "エージェント" in text:
        score += 1.0
    dt = item.get("published")
    if now is None:
        now = datetime.now(timezone.utc)
    if dt:
        age_h = (now - dt).total_seconds() / 3600.0
        if age_h < 24:
            score += 2.0
        elif age_h < 72:
            score += 1.0
    return score

def _dedup(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        key = re.sub(r"\W+", "", (it.get("title") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def run_curated(top_k: int = 5, per_feed: int = 10, use_snippet: bool = False) -> str:
    """
    複数RSS→スコア→重複排除→上位N件→記事単位要約→指定フォーマットで整形
    """
    items = fetch_all_rss(max_items_per_feed=per_feed, limit=200)
    # スコアリング
    now = datetime.now(timezone.utc)
    for it in items:
        it["_score"] = _score_item(it, now=now)
    # スコア/新しさ順に並べる
    items.sort(key=lambda x: (x["_score"], x.get("published") or datetime(1970, 1, 1, tzinfo=timezone.utc)), reverse=True)
    # 重複排除
    items = _dedup(items)
    # 上位だけ採用
    picks = items[:top_k]

    if not picks:
        local_today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
        return f"📅 {local_today}\n直近{NEWS_MAX_AGE_DAYS}日以内で条件に合うニュースは見つかりませんでした。"

    news_items = [NewsItem(title=it["title"], url=it.get("link")) for it in picks]
    article_summaries = summarize_articles(news_items, use_snippet=use_snippet)

    # ご指定のフォーマットで整形
    lines: List[str] = []
    for a in article_summaries:
        lines.append("【タイトル】")
        lines.append(a.title or "N/A")
        lines.append("【URL】")
        lines.append(a.url or "N/A")
        lines.append("【サマリー】")
        for b in a.bullets[:3]:
            lines.append(f"- {b}")
        lines.append("==========================================================================================")  # 区切り

    return "\n".join(lines).strip()
