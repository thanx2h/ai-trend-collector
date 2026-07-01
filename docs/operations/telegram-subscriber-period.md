# Telegram Subscriber Period Operations

This service is designed to run as a one-shot job.

## Environment

Set these environment variables:

- `AIDIGEST_TELEGRAM_BOT_TOKEN`
- `AIDIGEST_TELEGRAM_CHAT_ID`
- `AIDIGEST_DATABASE_URL`
- `AIDIGEST_DEFAULT_PERIOD_DAYS`
- `AIDIGEST_TIMEZONE_NAME`
- `AIDIGEST_ENABLED_SOURCES`

## Docker

Build the image:

```bash
docker build -t ai-trend-digest .
```

Run one cycle:

```bash
docker run --rm --env-file .env ai-trend-digest
```

The container runs `python -m aitrendigest.cli run-once`, processes new Telegram updates, and sends the digest to each subscriber who is due.

## Cron example

Run once per day at 09:00 local time:

```cron
0 9 * * * cd /opt/ai-trend-digest && docker run --rm --env-file .env ai-trend-digest
```

## Telegram commands

- Send any first message to register the chat.
- Send `/period N` to change that chat's delivery cadence.
- Use `/period 1` for daily delivery.
- Use `/period 7` for weekly delivery.
