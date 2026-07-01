# Telegram Subscriber Period Design

## Goal

Extend the current AI trend Telegram digest so multiple Telegram users can subscribe by messaging the bot, set their own delivery period with `/period N`, and receive the digest only on their own schedule.

This design assumes:

- deployment target is a Linux server notebook
- the app runs in Docker
- the app does not stay alive continuously
- cron starts the container at a fixed time, then the job exits

## Product Behavior

### Subscriber onboarding

- if a Telegram user sends any message to the bot for the first time, that `chat_id` is automatically registered
- the default period for a new subscriber is `1` day
- the default anchor date for a new subscriber is the current local date when the first message is processed

### Period command

The user can change their own schedule with:

```text
/period N
```

Examples:

- `/period 1` -> daily
- `/period 3` -> every 3 days
- `/period 7` -> weekly cadence by 7-day interval

Rules:

- `N` must be a positive integer
- when `/period N` is accepted, the subscriber's `period_days` becomes `N`
- when `/period N` is accepted, the subscriber's `anchor_date` resets to today
- the change applies only to the `chat_id` that sent the command

### Delivery rule

For each subscriber, the digest is sent only when today is on that subscriber's schedule.

A subscriber is eligible when:

- they are active
- they have a valid `period_days`
- the difference between `today` and `anchor_date` is divisible by `period_days`
- they have not already been sent a digest for `today`

Example:

- anchor date: `2026-07-01`
- period: `3`
- send dates: `2026-07-01`, `2026-07-04`, `2026-07-07`, ...

## Non-Goals

- real-time Telegram bot process
- webhook-based Telegram integration
- per-user topic personalization
- admin dashboard
- billing, quotas, or public multi-tenant controls

## Recommended Architecture

### 1. Scheduled runner

Use Linux cron to start a Docker container at a fixed time.

Recommended pattern:

- cron invokes `docker run` or `docker compose run`
- the container runs one command
- the command processes Telegram updates, sends digest messages as needed, then exits

This keeps the service simple and matches the user's operating preference.

### 2. Telegram update polling

Each scheduled run should call Telegram `getUpdates` and process only new updates.

Responsibilities:

- fetch updates from Telegram Bot API
- ignore already-processed updates
- extract `chat_id`, message text, and update id
- auto-register new subscribers
- apply supported commands such as `/period N`

To avoid duplicate command handling, the system must persist the latest processed `update_id`.

### 3. Subscriber store

Persist subscriber state in SQLite.

Recommended table: `subscribers`

Fields:

- `chat_id` primary key
- `is_active`
- `period_days`
- `anchor_date`
- `last_sent_on`
- `created_at`
- `updated_at`

Recommended table: `telegram_state`

Fields:

- `key`
- `value`

Initial use:

- store `last_update_id`

Optional table: `delivery_log`

Fields:

- `id`
- `chat_id`
- `sent_on`
- `message_hash`
- `status`
- `error_text`
- `created_at`

This is not required for the first iteration, but it is useful for debugging and replay safety.

### 4. Digest generation

Digest content can still be collected and ranked once per run, then reused across all eligible subscribers.

Recommended behavior:

- fetch source items once
- build one digest message for the run
- send the same digest payload to every eligible subscriber

This avoids repeated network fetches per subscriber and keeps execution time predictable.

### 5. Telegram publisher

Extend the current Telegram sender so it can send to arbitrary `chat_id` values rather than only one configured chat.

Responsibilities:

- send a message to a specific subscriber
- retry transient failures
- record success or failure in subscriber state and logs

## Execution Flow

For each scheduled run:

1. load settings and initialize storage
2. fetch new Telegram updates with `offset = last_update_id + 1`
3. process each update in order
4. auto-register unknown `chat_id` values
5. if a message matches `/period N`, validate and update that subscriber
6. persist the new `last_update_id`
7. fetch and rank digest source items once
8. compute which subscribers are eligible today
9. send the digest to each eligible subscriber
10. update `last_sent_on` for successful sends
11. exit

## Command Handling

### Supported commands for MVP

`/period N`

Success response example:

```text
Delivery period updated to every 3 days.
Next schedule is based on today.
```

Validation failures should return a friendly Telegram response.

Examples:

- `/period 0` -> reject
- `/period -1` -> reject
- `/period abc` -> reject
- `/period` -> reject

Suggested invalid usage response:

```text
Usage: /period 3
Send a positive number of days.
```

### Messages without commands

- if the sender is new, auto-register them
- no schedule change is applied
- optional response: brief confirmation that the subscription is active

## Time Model

The system should use one configured local timezone for schedule evaluation.

Initial recommendation:

- use the server's configured timezone, or an explicit app setting such as `Asia/Seoul`

Rules:

- `anchor_date` is stored as a date, not a datetime
- `last_sent_on` is stored as a date in the same timezone model
- schedule eligibility is computed from local dates only

This avoids subtle issues around send time drift.

## Failure Handling

### Telegram update polling failures

- if `getUpdates` fails, log the error and stop the run
- do not send the digest in a partially-known command state

### Source fetch failures

- tolerate partial source failures if enough content remains to build a digest
- if no usable items remain, skip sending and log the reason

### Message send failures

- retry 1 to 2 times for transient HTTP failures
- if a subscriber send still fails, do not update `last_sent_on`
- continue attempting delivery for the remaining eligible subscribers

## Docker And Operations

### Container behavior

The container should behave like a batch job.

Recommended command:

```text
python -m aitrendigest.cli run-once
```

This command should:

- process Telegram updates
- collect and rank digest items
- deliver to eligible subscribers
- exit with a non-zero code on fatal failure

### Cron behavior

Example shape:

```text
0 9 * * * docker run --rm --env-file /path/to/.env ai-trendigest:latest
```

The exact command can be refined during implementation.

## Security And Scope Controls

This is intended for personal or small private usage.

MVP guardrails:

- only process direct messages to the bot
- no group chat support in the first iteration
- no admin broadcast controls in the first iteration

## Data Model Summary

### subscribers

```text
chat_id: str
is_active: bool
period_days: int
anchor_date: date
last_sent_on: date | null
created_at: datetime
updated_at: datetime
```

### telegram_state

```text
key: str
value: str
```

### derived logic

```text
eligible_today =
  is_active
  and days_since_anchor % period_days == 0
  and last_sent_on != today
```

## Testing Strategy

Minimum coverage should include:

- auto-register on first message
- `/period N` updates only the sender's record
- invalid `/period` input returns an error message
- `last_update_id` prevents duplicate command handling
- eligibility calculation for daily and multi-day periods
- no duplicate send on the same date
- one digest payload reused across multiple subscribers
- partial send failure does not block other eligible subscribers

## Recommended Implementation Slices

### Slice 1

- restore or add subscriber-focused SQLite schema
- repository for subscriber state and Telegram state
- tests for persistence and eligibility logic

### Slice 2

- Telegram `getUpdates` client
- command parser for `/period N`
- auto-registration flow
- tests for update processing

### Slice 3

- multi-subscriber publish orchestration
- send to each eligible subscriber
- update `last_sent_on`
- tests for duplicate-send prevention

### Slice 4

- Dockerfile and runtime command
- Linux cron deployment docs
- smoke test instructions for the server notebook

## Recommendation

Proceed with:

- SQLite for subscriber state
- Telegram polling with `getUpdates`
- one scheduled Docker run per day
- one batch command that handles updates and delivery in a single process

This design matches the user's stated operating model while keeping the system understandable and easy to debug.
