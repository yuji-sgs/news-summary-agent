from dotenv import load_dotenv
import os

load_dotenv() # .envファイルから環境変数を自動で読み込む

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#general")
# RSS: 複数対応（NEWS_FEEDS優先、無ければNEWS_RSS）
NEWS_RSS = os.getenv("NEWS_RSS")
NEWS_FEEDS = [u.strip() for u in os.getenv("NEWS_FEEDS", "").split(",") if u.strip()]
if not NEWS_FEEDS and NEWS_RSS:
    NEWS_FEEDS = [NEWS_RSS]

DEFAULT_MODEL = os.getenv("MODEL", "gpt-5-nano")

# 好みキーワード（環境変数で上書き可能、カンマ区切り）

def _split_env(name, default_list=None):
    raw = os.getenv(name)
    if not raw:
        return default_list or []
    return [s.strip() for s in raw.split(",") if s.strip()]

PREF_PRIMARY   = _split_env("PREF_PRIMARY", [])
PREF_SECONDARY = _split_env("PREF_SECONDARY", [])
