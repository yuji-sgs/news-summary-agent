# agent/llm.py
from typing import List, Optional
from .config import OPENAI_API_KEY, DEFAULT_MODEL
from pydantic import BaseModel
from openai import OpenAI
from datetime import date
from .utils import logger
import json

client = OpenAI(api_key=OPENAI_API_KEY)

class NewsItem(BaseModel):
    title: str
    url: Optional[str] = None

class NewsSummary(BaseModel):
    date: str
    highlights: List[str]
    risks: List[str]
    opportunities: List[str]

SYSTEM = (
    "あなたは有能なアナリストです。本文は日本語で書きますが、"
    "出力JSONのキー名は英字のみ（date, highlights, risks, opportunities）に固定してください。"
    "キー名を日本語にしないでください。"
)

def _supports_temperature(model_name: str) -> bool:
    """一部モデル（o1/o3系やgpt-5*など）はtemperature非対応/固定"""
    lowered = model_name.lower()
    banned_prefixes = ("o1", "o3", "gpt-5")
    return not lowered.startswith(banned_prefixes)

# --- 整形ユーティリティ -------------------------------------------------

JP_TO_EN = {
    "日付": "date", "日時": "date",
    "ハイライト": "highlights", "要点": "highlights", "ポイント": "highlights",
    "リスク": "risks", "懸念": "risks",
    "機会": "opportunities", "チャンス": "opportunities",
}

def _normalize_keys(obj: dict) -> dict:
    """日本語キー等を英字キーへ正規化"""
    return {JP_TO_EN.get(k, k): v for k, v in obj.items()}

def _ensure_summary_shape(obj: dict) -> dict:
    """必須キーを補完し、配列型を保証"""
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

def _maybe_unwrap_articles(obj: dict) -> dict:
    """articles配列でラップされていれば先頭要素を採用"""
    if "articles" in obj and isinstance(obj["articles"], list) and obj["articles"]:
        return obj["articles"][0]
    return obj

# --- メイン -------------------------------------------------------------

def summarize_news(items: List[NewsItem]) -> NewsSummary:
    # 0件ならLLMは呼ばずに空の要約を返す
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
            - 記事が0件でも（または要約が難しくても）必ず上記キーを返し、配列は空配列にすること。
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

    resp = client.chat.completions.create(**params)
    raw = resp.choices[0].message.content or "{}"

    # なるべく中身を見たいときはデバッグをON
    # logger.debug(f"LLM raw: {raw[:500]}")

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("summarize_news: JSONDecodeError. raw=%s", raw[:500])
        obj = {}

    # 形の救済 → キー正規化 → 必須キー補完
    obj = _maybe_unwrap_articles(obj)
    obj = _normalize_keys(obj)
    obj = _ensure_summary_shape(obj)

    # dictでバリデーション（model_validate_jsonではなく）
    return NewsSummary.model_validate(obj)
