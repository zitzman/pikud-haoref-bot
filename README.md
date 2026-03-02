# Tzeva Adom → Slack Alert Bot

A production-ready service that polls the Israeli Home Front Command (Pikud HaOref) API for real-time rocket and emergency alerts and posts them to a Slack channel.

## Setup

### 1. Create a Slack Incoming Webhook

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App → From scratch**.
2. Choose a name (e.g. `Tzeva Adom Bot`) and select your workspace.
3. In the left sidebar, click **Incoming Webhooks** and toggle it **On**.
4. Click **Add New Webhook to Workspace**, choose a channel, and click **Allow**.
5. Copy the webhook URL — it looks like `https://hooks.slack.com/services/T.../B.../...`.

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and paste your webhook URL:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
POLL_INTERVAL=2
```

`POLL_INTERVAL` controls how often (in seconds) the Oref API is polled. The default is `2`.

### 3. Run with Docker Compose

```bash
docker compose up -d
```

The container will restart automatically on failure or system reboot (`restart: always`).

### View logs

```bash
docker compose logs -f
```

### Stop the bot

```bash
docker compose down
```

## Alert categories

| Category | Emoji | Type |
|----------|-------|------|
| 1 | 🚀 | Missiles / Rockets |
| 2 | 🛸 | UAV / Drone |
| 3 | 🌍 | Earthquake |
| 4 | ☣️ | Hazardous materials |
| 6 | 🌊 | Tsunami |
| 7 | ✈️ | Hostile aircraft |
| 13 | ☢️ | Nuclear |
| 101 | 🔫 | Terrorist infiltration |

## How it works

1. Every 2 seconds the bot polls `https://www.oref.org.il/WarningMessages/alert/alerts.json`.
2. If a new alert ID is detected, a Slack message is posted using Block Kit (header, affected cities, shelter instructions).
3. When the alert clears (empty response), the dedup state resets so the next alert is always posted.
4. On connection errors the bot backs off exponentially (5 s → 10 s → … → 60 s max).
