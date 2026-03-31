import time
from typing import Any, Dict

from news_pipeline.http_client import HTTP
from news_pipeline.storage.state_store import fetch_pending, mark_failed_attempt, mark_sent


def deliver_pending(config: Dict[str, Any], conn) -> None:
    delivery = config.get("delivery", {})
    webhook_url = config["webhook_url"]
    batch_size = int(delivery.get("batch_size", 20))
    max_attempts = int(delivery.get("max_attempts", 5))
    max_retries = int(delivery.get("max_retries", 3))
    retry_backoff_sec = float(delivery.get("retry_backoff_sec", 2))
    timeout_sec = int(delivery.get("timeout_sec", 15))

    while True:
        rows = fetch_pending(conn, batch_size)
        if not rows:
            break

        payload = {"items": [r["payload"] for r in rows]}
        sent = False
        last_err = ""

        for retry in range(max_retries + 1):
            try:
                resp = HTTP.post(webhook_url, json=payload, timeout=timeout_sec)
                if 200 <= resp.status_code < 300:
                    sent = True
                    break
                last_err = f"HTTP {resp.status_code}: {resp.text[:500]}"
            except Exception as ex:
                last_err = str(ex)
            if retry < max_retries:
                time.sleep(retry_backoff_sec * (2**retry))

        if sent:
            mark_sent(conn, [r["row_id"] for r in rows])
            print(f"[INFO] delivered batch size={len(rows)}")
        else:
            mark_failed_attempt(conn, rows, last_err, max_attempts)
            print(f"[ERROR] deliver batch failed size={len(rows)} err={last_err}")

