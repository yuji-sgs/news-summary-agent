from agent.notifiers import post_to_slack
from agent.curator import run_curated

if __name__ == "__main__":
    text = run_curated(top_k=5, per_feed=10)
    print(text)
    post_to_slack(text)
