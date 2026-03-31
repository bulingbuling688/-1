#!/usr/bin/env python3
import argparse
import sys

from news_pipeline.config import load_config
from news_pipeline.orchestrator import run_pipeline
from news_pipeline.storage import init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch news sources and push to n8n webhook.")
    parser.add_argument("--config", default="config.json", help="Path to config json.")
    parser.add_argument("--collect-only", action="store_true", help="Collect and enqueue only.")
    parser.add_argument("--deliver-only", action="store_true", help="Deliver pending only.")
    parser.add_argument("--retry-failed", action="store_true", help="Move failed items back to pending before delivery.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    conn = init_db(cfg.get("state_db", "collector_state.sqlite3"))
    return run_pipeline(
        config=cfg,
        conn=conn,
        collect_only=args.collect_only,
        deliver_only=args.deliver_only,
        retry_failed_first=args.retry_failed,
    )


if __name__ == "__main__":
    sys.exit(main())

