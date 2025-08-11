# agent/curator.py
import re
from datetime import datetime, timezone
from .io_sources import fetch_all_rss
from .llm import summarize_news, NewsItem
from .config import PREF_PRIMARY, PREF_SECONDARY

def _norm(s: str) -> str:
    return s.lower()

def _score_item(item: dict, now=None) -> float:
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
        if age_h < 24: score += 2.0
        elif age_h < 72: score += 1.0
    return score

def _dedup(items):
    seen = set()
    out = []
    for it in items:
        key = re.sub(r"\W+", "", it.get("title","").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def run_curated(top_k: int = 5, per_feed: int = 10) -> str:
    items = fetch_all_rss(max_items_per_feed=per_feed, limit=200)
    now = datetime.now(timezone.utc)
    for it in items:
        it["_score"] = _score_item(it, now=now)
    items.sort(key=lambda x: (x["_score"], x.get("published") or datetime(1970,1,1,tzinfo=timezone.utc)), reverse=True)
    items = _dedup(items)
    picks = items[:top_k]

    news_items = [NewsItem(title=it["title"], url=it.get("link")) for it in picks]
    summary = summarize_news(news_items)

    lines = [f"📅 {summary.date}"]
    lines.append("\n【ハイライト】")
    for h in summary.highlights: lines.append(f"・{h}")
    if summary.risks:
        lines.append("\n【リスク】")
        for r in summary.risks: lines.append(f"・{r}")
    if summary.opportunities:
        lines.append("\n【機会】")
        for o in summary.opportunities: lines.append(f"・{o}")

    lines.append("\n【今回の選定リンク（上位5件）】")
    for i, it in enumerate(picks, 1):
        src = f"（{it.get('source')}）" if it.get("source") else ""
        lines.append(f"{i}. {it.get('title')} {src}\n{it.get('link')}")
    return "\n".join(lines)
