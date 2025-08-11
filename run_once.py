from agent.processors import run_summary
from agent.notifiers import post_to_slack

if __name__ == "__main__":
    text = run_summary(top_n=6)
    print(text)
    post_to_slack(text)