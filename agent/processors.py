from .llm import summarize_news, NewsItem
from .io_sources import fetch_rss

def run_summary(top_n: int = 6):
    rss_items = fetch_rss(max_items=top_n)
    items = [NewsItem(title=i["title"], url=i.get("link")) for i in rss_items]
    summary = summarize_news(items)
    # 人間向けレンダリング
    lines = [f"📅 {summary.date}"]
    lines.append("\n【ハイライト】")
    for h in summary.highlights:
        lines.append(f"・{h}")
    if summary.risks:
        lines.append("\n【リスク】")
        for r in summary.risks:
            lines.append(f"・{r}")
    if summary.opportunities:
        lines.append("\n【機会】")
        for o in summary.opportunities:
            lines.append(f"・{o}")
    return "\n".join(lines)