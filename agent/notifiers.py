from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from .config import SLACK_BOT_TOKEN, SLACK_CHANNEL
from .utils import logger
from typing import Optional

client = WebClient(token=SLACK_BOT_TOKEN)

def post_to_slack(text: str, channel: Optional[str] = None):
    try:
        client.chat_postMessage(channel=channel or SLACK_CHANNEL, text=text)
        logger.info("Posted to Slack")
    except SlackApiError as e:
        logger.error(f"Slack error: {e.response['error']}")