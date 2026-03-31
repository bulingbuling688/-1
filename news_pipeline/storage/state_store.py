import json
import sqlite3
from typing import Any, Dict, List

from news_pipeline.utils import utc_now_iso


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_items (
          source_id TEXT PRIMARY KEY,
          source_name TEXT NOT NULL,
          first_seen_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS outbox (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_id TEXT NOT NULL UNIQUE,
          payload_json TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,
          last_error TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def add_to_outbox(conn: sqlite3.Connection, item: Dict[str, Any]) -> bool:
    source_id = item["source_id"]
    source_name = item["source_name"]
    now = utc_now_iso()

    cur = conn.execute("SELECT 1 FROM seen_items WHERE source_id = ?", (source_id,))
    if cur.fetchone():
        return False

    payload_json = json.dumps(item, ensure_ascii=False)
    with conn:
        conn.execute(
            "INSERT INTO seen_items(source_id, source_name, first_seen_at) VALUES(?,?,?)",
            (source_id, source_name, now),
        )
        conn.execute(
            """
            INSERT INTO outbox(source_id, payload_json, status, attempts, created_at, updated_at)
            VALUES(?, ?, 'pending', 0, ?, ?)
            """,
            (source_id, payload_json, now, now),
        )
    return True


def fetch_pending(conn: sqlite3.Connection, limit: int) -> List[Dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT id, payload_json, attempts FROM outbox
        WHERE status = 'pending'
        ORDER BY id ASC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    out = []
    for rid, payload_json, attempts in rows:
        out.append(
            {
                "row_id": rid,
                "payload": json.loads(payload_json),
                "attempts": attempts,
            }
        )
    return out


def mark_sent(conn: sqlite3.Connection, row_ids: List[int]) -> None:
    now = utc_now_iso()
    with conn:
        conn.executemany(
            "UPDATE outbox SET status='sent', updated_at=?, last_error=NULL WHERE id=?",
            [(now, rid) for rid in row_ids],
        )


def mark_failed_attempt(conn: sqlite3.Connection, rows: List[Dict[str, Any]], err: str, max_attempts: int) -> None:
    now = utc_now_iso()
    with conn:
        for r in rows:
            attempts = int(r["attempts"]) + 1
            status = "failed" if attempts >= max_attempts else "pending"
            conn.execute(
                """
                UPDATE outbox
                SET attempts=?, status=?, last_error=?, updated_at=?
                WHERE id=?
                """,
                (attempts, status, err[:1000], now, r["row_id"]),
            )


def requeue_failed(conn: sqlite3.Connection) -> int:
    now = utc_now_iso()
    with conn:
        cur = conn.execute(
            "UPDATE outbox SET status='pending', updated_at=? WHERE status='failed'",
            (now,),
        )
    return cur.rowcount


def summary(conn: sqlite3.Connection) -> None:
    pending = conn.execute("SELECT COUNT(*) FROM outbox WHERE status='pending'").fetchone()[0]
    sent = conn.execute("SELECT COUNT(*) FROM outbox WHERE status='sent'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM outbox WHERE status='failed'").fetchone()[0]
    print(f"[SUMMARY] sent={sent} pending={pending} failed={failed}")

