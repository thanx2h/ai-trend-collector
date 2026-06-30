# AI Trend Telegram Digest Design

## Goal

Build a personal AI trend digest that collects current AI engineering signals, stores them, ranks them, and sends one Telegram summary per day with direct links to detailed sources.

The product is not a general news reader. Its job is to help the user quickly see what is trending now and decide what is worth trying in practice.

## Product Shape

- Delivery channel: Telegram
- Delivery cadence: one digest per day
- Digest content:
  - top 3 to 7 items for the day
  - one-line summary per item
  - short "why it matters" note
  - tags such as `agent`, `eval`, `infra`, `multimodal`
  - direct links to original sources such as articles, papers, repos, or videos
  - one short "things to try" section at the end
- Source scope for MVP:
  - GitHub Trending
  - Hugging Face Trending Models
  - Hugging Face Trending Papers
  - arXiv
  - selected blogs and newsletters
  - selected YouTube sources related to AI engineering

## Non-Goals For MVP

- full web dashboard
- real-time alerts
- personalized recommendations from click history
- complex agent workflows
- social network ingestion such as X or Reddit

## User Outcome

Each day, the user should be able to open one Telegram message and answer:

- What is hot right now in AI engineering?
- Why does it matter?
- What should I read or watch next?
- What is worth trying this week?

## Architecture

The system is split into four components.

### 1. Collector

Responsibility:

- fetch source data on a schedule
- normalize source-specific fields into a common schema
- tolerate partial source failures

Initial source adapters:

- `github_trending`
- `hf_trending_models`
- `hf_trending_papers`
- `arxiv`
- `rss_blog`
- `youtube_channel` or `youtube_feed`

Collector schedule:

- run 2 to 4 times per day
- store every fetch result
- do not send Telegram messages directly

### 2. Store

Responsibility:

- persist normalized items
- track source metadata
- deduplicate repeated items
- track publish and send status

Initial storage choice:

- `SQLite`

Reason:

- low setup cost
- enough for a single-user MVP
- easy migration path later to Postgres

### 3. Ranker And Summarizer

Responsibility:

- compute a daily priority score
- cluster duplicate or near-duplicate items
- generate short summaries
- choose final items for the digest

Initial scoring dimensions:

- `freshness`
- `source_popularity`
- `practical_value`
- `cross_source_mentions`

Initial score formula:

```text
final_score =
0.30 * freshness
+ 0.25 * source_popularity
+ 0.25 * practical_value
+ 0.20 * cross_source_mentions
```

Notes:

- each dimension is normalized to a common `0.0` to `1.0` scale
- `source_popularity` is computed from source-specific public signals
- the formula is intentionally simple and explainable for MVP

Summary output fields:

- `title`
- `source`
- `url`
- `published_at`
- `tags`
- `score`
- `summary`
- `why_it_matters`
- optional `related_sources`

### 4. Telegram Publisher

Responsibility:

- build the final digest message
- send it once per day
- retry on transient failures
- mark send status in storage

Digest format:

```text
[AI Trend Digest | 2026-06-26]

1. Title
Tag: agent, eval
Why: short practical reason
Link: original URL

2. Title
Tag: infra, serving
Why: short practical reason
Link: original URL

Try This Today
- one or two concrete experiments
```

## Canonical Data Model

Each collected item should map into one normalized record.

```text
TrendItem
- id
- source_type
- source_name
- source_item_id
- title
- url
- author
- published_at
- fetched_at
- raw_popularity_signal
- normalized_popularity_score
- summary
- why_it_matters
- tags
- topic_fingerprint
- duplicate_group_id
- final_score
- send_status
```

## Deduplication

The system should reduce repeated noise before ranking.

Rules:

- exact URL duplicates collapse into one record group
- same GitHub repo from multiple fetches collapses into one current item
- same paper referenced by multiple sources can be grouped by canonical URL or title similarity
- when one topic appears across multiple sources, keep one primary item and list the others as related sources

The MVP should prefer deterministic deduplication over fuzzy heuristics that are hard to debug.

## Tagging

Initial controlled vocabulary:

- `agent`
- `eval`
- `rag`
- `infra`
- `multimodal`
- `serving`
- `tooling`
- `skill`
- `data`
- `voice`
- `video`
- `security`

Tagging can begin rule-based:

- keyword rules
- source-specific hints
- optional LLM refinement later

## Source Popularity Signals

Popularity should be derived from visible source-native signals, then normalized.

Examples:

- GitHub Trending:
  - trending position
  - stars
  - forks
  - recent star growth if available
- Hugging Face:
  - trending placement
  - likes
  - downloads if available
- arXiv:
  - weak direct popularity, so rely more on cross-source mentions
- blogs and newsletters:
  - no strong native popularity, so use freshness plus cross-source repetition
- YouTube:
  - view count
  - upload recency
  - channel relevance

## Practical Value Heuristic

The digest should prefer items the user can apply, not just admire.

Signals that increase `practical_value`:

- code repository exists
- runnable demo exists
- tutorial or implementation notes exist
- operational topic such as evals, serving, observability, tool use, document parsing
- reusable pattern, framework, or benchmark

Signals that decrease `practical_value`:

- purely promotional content
- vague opinion posts with no artifact or technique
- stale content with no current relevance

## Scheduling

Two schedules are required.

- collection schedule:
  - 2 to 4 times per day
- publish schedule:
  - once per day at a configurable local time

The publish job should always read from stored items, never from live fetch results directly.

## Error Handling

- one failing source must not block the whole pipeline
- if summary generation fails, fall back to title plus link
- if Telegram send fails, retry 1 to 2 times and mark error state
- if the publish job reruns, already-sent items must not be sent again
- if no high-quality items exist, send a shorter digest instead of failing

## Configuration

Environment variables should cover:

- Telegram bot token
- Telegram chat id
- digest send time
- enabled sources
- source-specific feed or channel configuration
- optional LLM API key for later summarization improvements

## Observability

The MVP does not need a full dashboard, but it does need basic traceability.

Required logs:

- collector start and end
- per-source success or failure
- number of new items
- number of deduplicated groups
- number of ranked items
- send success or send failure

Useful admin outputs later:

- recent run summary
- top items before publishing
- failed items by source

## Quality Bar

The system is successful when:

- the user receives one digest per day reliably
- the digest is short enough to scan quickly
- every item has a valid direct link
- the selected items feel timely and relevant
- repeated noise is reduced
- the ranking logic is simple enough to explain and tune

## Suggested Tech Stack

- language: Python
- HTTP: `httpx`
- parsing: `feedparser`, `BeautifulSoup`
- storage: `SQLite`
- ORM or DB layer: `SQLAlchemy`
- scheduler: system scheduler or lightweight in-app scheduler
- Telegram integration: Bot API

## MVP Build Order

1. create common data model and storage
2. implement collectors for core sources
3. add deterministic deduplication
4. implement rule-based scoring
5. implement digest formatting
6. send Telegram digest manually
7. enable scheduled collection and daily publish

## Risks And Mitigations

- source HTML structure changes
  - keep adapters isolated per source
- noisy or low-value content
  - keep source list curated and use practical-value weighting
- overcomplicated ranking too early
  - keep scoring rule-based for MVP
- duplicate overload across sources
  - prioritize canonical URL and repo or paper identity rules first

## Future Extensions

- web dashboard for archive and filtering
- personal feedback loop from saved or clicked items
- topic heatmap by week
- trend change detection across time
- experimental auto-generated "what to try this week" section
- richer clustering of the same topic across sources

## Decision Summary

The chosen design is:

- `Python + SQLite + Telegram bot`
- one daily digest
- multiple daily collection runs
- rules-based scoring with source-native popularity signals
- stored history for future dashboard expansion
