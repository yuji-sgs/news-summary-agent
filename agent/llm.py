from typing import List, Optional
from .config import OPENAI_API_KEY, DEFAULT_MODEL
from pydantic import BaseModel
from openai import OpenAI
import json
from datetime import date

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
    """
    一部モデル（例：o1/o3系や一部の最新モデル）は温度パラメータ非対応/固定なので付与しない
    """
    lowered = model_name.lower()
    banned_prefixes = ("o1", "o3", "gpt-5")
    return not lowered.startswith(banned_prefixes)

def summarize_news(items: List[NewsItem]) -> NewsSummary:
    """
    ニュース記事リストを要約し、NewsSummary形式で返す
    """
    # Structured Output（JSON）
    user = f"""次のニュース見出しとURLを要約してください。
            - 出力は必ずトップレベルのJSONオブジェクトで、次のキーのみを持つこと: ["date","highlights","risks","opportunities"]
            - 配列や別キー（例: "articles" など）でラップしないこと。
            - date は YYYY-MM-DD で今日の日付。
            - highlights は3〜5個、risks/opportunities は各2〜4個。

            {json.dumps([i.model_dump() for i in items], ensure_ascii=False)}
            """

    params = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user}
        ],
        "response_format": {"type": "json_object"},
    }
    if _supports_temperature(DEFAULT_MODEL):
        params["temperature"] = 0.2

    resp = client.chat.completions.create(**params)
    raw = resp.choices[0].message.content

    # JSONパース
    obj = json.loads(raw)

    def _coerce_to_summary(o: dict) -> dict:
        # すでに理想形
        need = {"date", "highlights", "risks", "opportunities"}
        if need.issubset(o.keys()):
            return o

        # articles でラップされている場合の救済
        if isinstance(o.get("articles"), list) and o["articles"]:
            a0 = o["articles"][0]
            return {
                "date": a0.get("date") or date.today().isoformat(),
                "highlights": a0.get("highlights") or [],
                "risks": a0.get("risks") or [],
                "opportunities": a0.get("opportunities") or [],
            }

        raise ValueError(f"Unexpected JSON shape: keys={list(o.keys())}")

    obj = _coerce_to_summary(obj)
    return NewsSummary.model_validate(obj)  # dictで直接検証
