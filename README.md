# Pikud HaOref → Slack Alert Bot

Polls the Israeli Home Front Command (Pikud HaOref) API for real-time rocket and emergency alerts and posts them to a Slack channel.

## Architecture

| Deployment | How | Polling interval | Cost |
|------------|-----|-----------------|------|
| **AWS Lambda** (recommended) | EventBridge triggers Lambda every minute in `il-central-1` (Tel Aviv) | 1 min | Free tier |
| **Docker / local** | Long-running container, polling loop | Configurable (default 10s) | Self-hosted |

> The Oref API blocks requests from non-Israeli IPs. AWS `il-central-1` (Tel Aviv) works reliably.

---

## Option A — AWS Lambda (recommended)

### 1. Create a Slack Incoming Webhook

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App → From scratch**
2. Name it (e.g. `Pikud HaOref Bot`) and select your workspace
3. Sidebar → **Incoming Webhooks** → toggle **On**
4. **Add New Webhook to Workspace** → choose a channel → **Allow**
5. Copy the webhook URL: `https://hooks.slack.com/services/T.../B.../...`

### 2. Create an AWS IAM user for deployments

1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam) → **Users → Create user**
2. Name: `github-actions-deployer`
3. **Attach policies directly** — add all of:
   - `AWSLambdaFullAccess`
   - `AmazonSSMFullAccess`
   - `CloudFormationFullAccess`
   - `IAMFullAccess`
   - `AmazonS3FullAccess`
   - `AmazonEventBridgeFullAccess`
4. Create an **Access Key** → use case: **Third-party service** → copy the Key ID and Secret

### 3. Add GitHub repository secrets

Go to **github.com/zitzman/pikud-haoref-bot → Settings → Secrets → Actions → New secret**:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | from step 2 |
| `AWS_SECRET_ACCESS_KEY` | from step 2 |
| `SLACK_WEBHOOK_URL` | from step 1 |

### 4. Deploy

Push any change to `main` — GitHub Actions will build and deploy automatically to `il-central-1`.

To trigger a manual redeploy:
```bash
git commit --allow-empty -m "Trigger redeploy" && git push
```

### 5. View logs

**AWS Console → Lambda → `pikud-haoref-bot` → Monitor → View CloudWatch logs**

Or: **CloudWatch → Log groups → `/aws/lambda/pikud-haoref-bot`**

> Make sure the region is set to **il-central-1 (Tel Aviv)**.

---

## Option B — Docker (local / self-hosted)

> Only works from an Israeli IP. Suitable for running on a home server in Israel.

### 1. Configure environment variables

```bash
cp .env.example .env
# Edit .env and set SLACK_WEBHOOK_URL
```

### 2. Run

```bash
docker compose up -d
docker compose logs -f
```

### Stop

```bash
docker compose down
```

---

## Testing

Send a fake alert to Slack without waiting for a real one:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/... python3 test_alert.py
```

---

## Alert categories

| Emoji | Type |
|-------|------|
| 🚀 | Missile / Rocket fire |
| 🛸 | UAV / Drone intrusion |
| ✈️ | Hostile aircraft |
| 🌍 | Earthquake |
| ☣️ | Hazardous materials |
| 🌊 | Tsunami |
| ☢️ | Nuclear threat |
| 🔫 | Terrorist infiltration |

Alert titles and shelter instructions are translated from the Hebrew API response. City names are translated where known and fall back to Hebrew for unmapped locations.

---

## How it works

1. **AWS Lambda** is triggered by EventBridge every minute
2. The function fetches `https://www.oref.org.il/WarningMessages/alert/alerts.json`
3. The last-seen alert ID is stored in **SSM Parameter Store** for deduplication
4. On a new alert: formats a Slack Block Kit message and POSTs to the webhook
5. When the alert clears (empty response): resets SSM state so the next alert always fires
