"""Send a fake alert to Slack to verify the webhook and message formatting."""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Must set env var before importing main (it reads it at module level)
os.environ.setdefault("SLACK_WEBHOOK_URL", os.environ.get("SLACK_WEBHOOK_URL", ""))

from main import format_slack_message, post_to_slack

FAKE_ALERT = {
    "id": "TEST-001",
    "cat": "1",
    "title": "ירי רקטות וטילים",
    "data": ["אשקלון", "אשדוד", "קריית גת"],
    "desc": "היכנסו למרחב המוגן ושהו בו 10 דקות",
}

if __name__ == "__main__":
    print("Sending test alert to Slack...")
    slack_payload = format_slack_message(FAKE_ALERT)
    post_to_slack(slack_payload)
    print("Done. Check your Slack channel.")
