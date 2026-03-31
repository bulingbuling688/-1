# Host Collector (PC -> n8n)

This script runs on your local machine:
- Collects news from configured sources
- Deduplicates with SQLite
- Pushes batches to n8n Webhook

## Modular Layout

`news_pipeline/collectors/`
- `hn.py`: Hacker News collector
- `rss.py`: RSS collector
- `raingou.py`: Raingou ranking collector (`/api/s?id=...`)

`news_pipeline/processors/`
- `content_enricher.py`: full-text enrichment (best effort)

`news_pipeline/storage/`
- `state_store.py`: seen/outbox persistence, retries, summary

`news_pipeline/delivery/`
- `webhook.py`: webhook delivery with retry/backoff

`news_pipeline/plugins/` (reserved, no-op for now)
- `translator.py`
- `entity_linker.py`
- `topic_cluster.py`
- `personalizer.py`

## 1) Install

```bash
python -m pip install -r requirements.txt
```

## 2) Configure

Copy and edit:

```bash
copy config.example.json config.json
```

Set your real `webhook_url` in `config.json`.
Use `enabled: true/false` on each source to enable/disable modules without deleting them.

## 3) Run

```bash
python collector.py --config config.json
```

Useful modes:

```bash
python collector.py --config config.json --collect-only
python collector.py --config config.json --deliver-only
python collector.py --config config.json --retry-failed --deliver-only
```

## 4) Payload to n8n

POST JSON body:

```json
{
  "items": [
    {
      "source_id": "hn:123",
      "source_name": "hackernews",
      "title": "...",
      "url": "...",
      "domain": "...",
      "author": "...",
      "published_at": "...",
      "content_snippet": "...",
      "score": 10,
      "raw": {},
      "fetched_at": "..."
    }
  ]
}
```
