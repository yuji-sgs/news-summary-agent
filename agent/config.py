from dotenv import load_dotenv
import os

load_dotenv() # .envファイルから環境変数を自動で読み込む

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#general")
NEWS_RSS = os.getenv("NEWS_RSS")
DEFAULT_MODEL = os.getenv("MODEL", "gpt-5-nano")