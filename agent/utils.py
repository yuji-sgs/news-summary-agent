from loguru import logger
from tenacity import retry, wait_exponential, stop_after_attempt

# ログをagent.logに保存
logger.add("agent.log", rotation="1 week", retention="4 weeks", level="INFO")

# ネットワーク系は指数バックオフ
retry_net = retry(wait=wait_exponential(multiplier=1, min=1, max=10),
                  stop=stop_after_attempt(3), reraise=True)