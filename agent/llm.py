from typing import List, Optional
from .config import OPENAI_API_KEY, DEFAULT_MODEL
from pydantic import BaseModel
from openai import OpenAI
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
    "あなたは有能なアナリストです。必ず日本語で、指定のJSONスキーマに沿って出力してください。"
)

def _supports_temperature(model_name: str) -> bool:
    # 一部モデル（例：o1/o3系や一部の最新モデル）は温度パラメータ非対応/固定
    lowered = model_name.lower()
    banned_prefixes = ("o1", "o3", "gpt-5")
    return not lowered.startswith(banned_prefixes)

def summarize_news(items: List[NewsItem]) -> NewsSummary:
    # Structured Output（JSON）
    user = f"""次のニュース見出しとURLを要約してください。
            - 日付はYYYY-MM-DDで今日の日付にしてください。
            - highlightsは3〜5個、risks/opportunitiesは各2〜4個。
            - 出力は必ずJSONのみ。

            {json.dumps([i.model_dump() for i in items], ensure_ascii=False)}
            """

    params = {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    if _supports_temperature(DEFAULT_MODEL):
        params["temperature"] = 0.2

    resp = client.chat.completions.create(**params)
    data = resp.choices[0].message.content

    # Pydanticでバリデーション
    return NewsSummary.model_validate_json(data)