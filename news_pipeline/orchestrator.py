from typing import Any, Dict

from news_pipeline.delivery import deliver_pending
from news_pipeline.processors import enrich_content
from news_pipeline.source_registry import collect_all
from news_pipeline.storage import add_to_outbox, requeue_failed, summary


def run_pipeline(
    config: Dict[str, Any],
    conn,
    collect_only: bool = False,
    deliver_only: bool = False,
    retry_failed_first: bool = False,
) -> int:
    timeout_sec = int(config.get("fetch_timeout_sec", 15))

    if retry_failed_first:
        n = requeue_failed(conn)
        print(f"[INFO] requeued_failed={n}")

    if not deliver_only:
        items = collect_all(config, timeout_sec)
        enrich_content(items, config)
        added = 0
        for item in items:
            if add_to_outbox(conn, item):
                added += 1
        print(f"[INFO] collected_total={len(items)} new_enqueued={added}")

    if not collect_only:
        deliver_pending(config, conn)

    summary(conn)
    return 0

