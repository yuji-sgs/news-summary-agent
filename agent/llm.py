from typing import List, Optional
from .config import OPENAI_API_KEY, DEFAULT_MODEL
from pydantic import BaseModel
from openai import OpenAI
from datetime import date
from .utils import logger
import json

client = OpenAI(api_key=OPENAI_API_KEY)

# ---- モデル定義 ---------------------------------------------------------

class NewsItem(BaseModel):
    title: str
    url: Optional[str] = None

class NewsSummary(BaseModel):
    date: str
    highlights: List[str]
    risks: List[str]
    opportunities: List[str]

class ArticleSummary(BaseModel):
    title: str
    url: Optional[str] = None
    bullets: List[str]

# ---- プロンプト / ユーティリティ ---------------------------------------

SYSTEM = (
    "あなたは有能なアナリストです。本文は日本語で書きますが、"
    "出力JSONのキー名は英字のみ（date, highlights, risks, opportunities あるいは title, url, bullets）に固定してください。"
    "キー名を日本語にしないでください。"
)

def _supports_temperature(model_name: str) -> bool:
    """一部モデル（o1/o3系やgpt-5*など）はtemperature非対応/固定"""
    lowered = model_name.lower()
    banned_prefixes = ("o1", "o3", "gpt-5")
    return not lowered.startswith(banned_prefixes)

# JSONキー正規化（日本語などを英字に寄せる）
JP_TO_EN = {
    # NewsSummary系
    "日付": "date", "日時": "date",
    "ハイライト": "highlights", "要点": "highlights", "ポイント": "highlights",
    "リスク": "risks", "懸念": "risks",
    "機会": "opportunities", "チャンス": "opportunities",
    # ArticleSummary系
    "タイトル": "title",
    "URL": "url", "Url": "url", "リンク": "url",
    "サマリー": "bullets", "要約": "bullets", "箇条書き": "bullets",
}

def _normalize_keys(obj: dict) -> dict:
    return {JP_TO_EN.get(k, k): v for k, v in obj.items()}

def _ensure_summary_shape(obj: dict) -> dict:
    """NewsSummaryの必須キーを補完し、配列型を保証"""
    out = {
        "date": obj.get("date") or date.today().isoformat(),
        "highlights": obj.get("highlights") or [],
        "risks": obj.get("risks") or [],
        "opportunities": obj.get("opportunities") or [],
    }
    for k in ("highlights", "risks", "opportunities"):
        v = out[k]
        if isinstance(v, str):
            out[k] = [v] if v.strip() else []
        elif not isinstance(v, list):
            out[k] = []
    return out

def _ensure_article_shape(obj: dict, fallback_title: str, fallback_url: Optional[str]) -> dict:
    """ArticleSummaryの必須キーを補完し、bulletsを3件に整える"""
    title = obj.get("title") or fallback_title
    url = obj.get("url") or fallback_url
    bullets = obj.get("bullets") or []
    if isinstance(bullets, str):
        bullets = [bullets] if bullets.strip() else []
    # 文字列以外は落とす
    bullets = [b for b in bullets if isinstance(b, str) and b.strip()]
    # 3件に切り詰め/補完
    bullets = bullets[:3]
    while len(bullets) < 3:
        bullets.append("（要約情報が不足しています）")
    return {"title": title, "url": url, "bullets": bullets}

def _maybe_unwrap_articles(obj: dict) -> dict:
    """articles配列でラップされていれば先頭要素を採用"""
    if "articles" in obj and isinstance(obj["articles"], list) and obj["articles"]:
        return obj["articles"][0]
    return obj

def _chat(params: dict):
    """必要に応じてフォールバック（gpt-5-nano失敗時に4o-miniへ）"""
    try:
        return client.chat.completions.create(**params)
    except Exception as e:
        if params.get("model") == "gpt-5-nano":
            params = dict(params)
            params["model"] = "gpt-4o-mini"
            params.pop("temperature", None)
            return client.chat.completions.create(**params)
        raise

# ---- 集約要約（既存のハイライト/リスク/機会） ---------------------------

def summarize_news(items: List[NewsItem]) -> NewsSummary:
    # 0件なら空で返す
    if not items:
        logger.info("summarize_news: items is empty; returning empty summary.")
        return NewsSummary(
            date=date.today().isoformat(),
            highlights=[],
            risks=[],
            opportunities=[],
        )

    user = f"""次のニュース見出しとURLを要約してください。
- 出力は必ずトップレベルのJSONオブジェクトで、キーは英字で次の4つのみ:
  ["date","highlights","risks","opportunities"]
- 配列や別キー（例: "articles" など）でラップしないこと。
- 記事が0件でも必ず上記キーを返し、配列は空配列にすること。
- date は YYYY-MM-DD で今日の日付。
- highlights は3〜5個、risks/opportunities は各2〜4個。

{json.dumps([i.model_dump() for i in items], ensure_ascii=False)}
"""

    params = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    if _supports_temperature(DEFAULT_MODEL):
        params["temperature"] = 0.2

    resp = _chat(params)
    raw = resp.choices[0].message.content or "{}"
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("summarize_news: JSONDecodeError. raw=%s", raw[:500])
        obj = {}

    obj = _maybe_unwrap_articles(obj)
    obj = _normalize_keys(obj)
    obj = _ensure_summary_shape(obj)

    return NewsSummary.model_validate(obj)

# ---- 記事単位の要約（ご指定フォーマット用） ------------------------------

def summarize_article(item: NewsItem, use_snippet: bool = False) -> ArticleSummary:
    """
    単一記事の3点要約を返す（title/url/bullets）
    use_snippet=True にすると本文スニペットも投げます（コスト増）
    """
    snippet = ""
    if use_snippet and item.url:
        try:
            from .io_sources import fetch_article_text  # 循環import回避のためローカルimport
            snippet = (fetch_article_text(item.url) or "")[:600]
        except Exception as e:
            logger.warning(f"summarize_article: snippet fetch failed: {e}")

    user = f"""次の記事について、以下のJSON形式で出力してください。
- キー名は英字で固定: ["title","url","bullets"]
- bulletsは日本語で3項目、簡潔に（1項目30字程度）
- JSON以外のテキストは出力しない

記事情報:
{json.dumps(item.model_dump(), ensure_ascii=False)}

本文抜粋:
{snippet}
"""

    params = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content":
             "あなたは日本語で要約を書くが、JSONのキー名は必ず英字（title,url,bullets）に固定する。"},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    if _supports_temperature(DEFAULT_MODEL):
        params["temperature"] = 0.2

    resp = _chat(params)
    raw = resp.choices[0].message.content or "{}"
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        obj = {}

    obj = _maybe_unwrap_articles(obj)
    obj = _normalize_keys(obj)
    obj = _ensure_article_shape(obj, fallback_title=item.title, fallback_url=item.url)

    return ArticleSummary.model_validate(obj)

def summarize_articles(items: List[NewsItem], use_snippet: bool = False) -> List[ArticleSummary]:
    return [summarize_article(it, use_snippet=use_snippet) for it in items]
