import argparse
import base64
import json
import os
import re
import sqlite3
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from news_pipeline.config import load_config
from news_pipeline.http_client import HTTP
from news_pipeline.orchestrator import run_pipeline
from news_pipeline.storage import init_db


WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _slug(s: str, max_len: int = 50) -> str:
    s = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", (s or "").strip())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s or "untitled")[:max_len]


def _query_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    return {
        "sent": conn.execute("SELECT COUNT(*) FROM outbox WHERE status='sent'").fetchone()[0],
        "pending": conn.execute("SELECT COUNT(*) FROM outbox WHERE status='pending'").fetchone()[0],
        "failed": conn.execute("SELECT COUNT(*) FROM outbox WHERE status='failed'").fetchone()[0],
        "seen": conn.execute("SELECT COUNT(*) FROM seen_items").fetchone()[0],
    }


def _query_recent(conn: sqlite3.Connection, status: str, limit: int) -> List[Dict[str, Any]]:
    status = status if status in {"sent", "pending", "failed"} else "sent"
    limit = max(1, min(limit, 100))
    rows = conn.execute(
        """
        SELECT id, source_id, payload_json, status, attempts, updated_at
        FROM outbox
        WHERE status=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (status, limit),
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for rid, source_id, payload_json, st, attempts, updated_at in rows:
        payload = json.loads(payload_json)
        out.append(
            {
                "id": rid,
                "source_id": source_id,
                "status": st,
                "attempts": attempts,
                "updated_at": updated_at,
                "title": payload.get("title", ""),
                "url": payload.get("url", ""),
                "source_name": payload.get("source_name", ""),
                "published_at": payload.get("published_at"),
            }
        )
    return out


class RunState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = False
        self.last_started_at = None
        self.last_finished_at = None
        self.last_mode = None
        self.last_error = None
        self.last_ok = None
        self.last_duration_sec = None

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "running": self.running,
                "last_started_at": self.last_started_at,
                "last_finished_at": self.last_finished_at,
                "last_mode": self.last_mode,
                "last_error": self.last_error,
                "last_ok": self.last_ok,
                "last_duration_sec": self.last_duration_sec,
            }

    def start(self, mode: str) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.last_mode = mode
            self.last_started_at = int(time.time())
            self.last_finished_at = None
            self.last_error = None
            self.last_ok = None
            self.last_duration_sec = None
            return True

    def finish(self, ok: bool, err: str | None = None) -> None:
        with self.lock:
            self.running = False
            self.last_finished_at = int(time.time())
            self.last_ok = ok
            self.last_error = err
            if self.last_started_at:
                self.last_duration_sec = self.last_finished_at - self.last_started_at


def _run_with_mode(config_path: str, mode: str, run_state: RunState) -> None:
    try:
        cfg = load_config(config_path)
        conn = init_db(cfg.get("state_db", "collector_state.sqlite3"))
        kwargs: Dict[str, Any] = {
            "collect_only": False,
            "deliver_only": False,
            "retry_failed_first": False,
        }
        if mode == "collect":
            kwargs["collect_only"] = True
        elif mode == "deliver":
            kwargs["deliver_only"] = True
        elif mode == "retry_deliver":
            kwargs["retry_failed_first"] = True
            kwargs["deliver_only"] = True
        run_pipeline(config=cfg, conn=conn, **kwargs)
        conn.close()
        run_state.finish(True, None)
    except Exception as ex:
        run_state.finish(False, str(ex))


def _save_local_article(cfg: Dict[str, Any], payload: Dict[str, Any]) -> str:
    storage_cfg = cfg.get("github_storage", {})
    local_dir = storage_cfg.get("local_backup_dir", "generated_articles")
    out_dir = Path(local_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    article = payload.get("article", {})
    title = str(article.get("title_cn") or payload.get("input_meta", {}).get("title") or "article")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{ts}_{_slug(title)}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def _save_to_github(cfg: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    storage_cfg = cfg.get("github_storage", {})
    if not storage_cfg.get("enabled", False):
        return {"ok": False, "skipped": True, "reason": "github_storage.enabled=false"}

    repo = str(storage_cfg.get("repo", "")).strip()
    if not repo or "/" not in repo:
        return {"ok": False, "error": "github_storage.repo must be owner/repo"}

    token_env = str(storage_cfg.get("token_env", "GITHUB_TOKEN"))
    token = os.getenv(token_env, "").strip()
    if not token:
        return {"ok": False, "error": f"missing env var: {token_env}"}

    branch = str(storage_cfg.get("branch", "main"))
    path_prefix = str(storage_cfg.get("path_prefix", "generated_articles")).strip().strip("/")
    article = payload.get("article", {})
    title = str(article.get("title_cn") or "article")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = f"{path_prefix}/{ts}_{_slug(title)}.json"

    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    b64 = base64.b64encode(content).decode("ascii")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    body = {
        "message": f"add generated article: {title[:40]}",
        "content": b64,
        "branch": branch,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = HTTP.put(url, json=body, headers=headers, timeout=30)
    if 200 <= resp.status_code < 300:
        j = resp.json() if resp.text else {}
        return {
            "ok": True,
            "repo": repo,
            "branch": branch,
            "path": path,
            "url": j.get("content", {}).get("html_url"),
        }
    return {"ok": False, "status": resp.status_code, "error": resp.text[:500]}


def _call_ai_webhook(cfg: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    ai_cfg = cfg.get("ai", {})
    webhook_url = str(ai_cfg.get("webhook_url", "")).strip()
    if not webhook_url:
        raise ValueError("ai.webhook_url is not configured")
    timeout_sec = int(ai_cfg.get("timeout_sec", 120))

    payload = {
        "title": body.get("title", ""),
        "source": body.get("source", ""),
        "url": body.get("url", ""),
        "content": body.get("content", ""),
        "prompt": body.get("prompt", ""),
        "audience": body.get("audience", "General readers"),
        "tone": body.get("tone", "Professional and concise"),
        "model": body.get("model", ai_cfg.get("model", "gpt-4.1-mini")),
    }
    resp = HTTP.post(webhook_url, json=payload, timeout=timeout_sec)
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"AI webhook failed: HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        return resp.json()
    except Exception:
        return {"ok": False, "raw": resp.text}


def make_handler(config_path: str, db_path: str, run_state: RunState):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, obj: Dict[str, Any], status: int = 200) -> None:
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _send_file(self, path: Path, content_type: str) -> None:
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _parse_limit_status(self) -> Tuple[str, int]:
            q = parse_qs(urlparse(self.path).query)
            status = (q.get("status", ["sent"])[0] or "sent").strip()
            try:
                limit = int(q.get("limit", ["20"])[0])
            except ValueError:
                limit = 20
            return status, limit

        def _body_json(self) -> Dict[str, Any]:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0:
                return {}
            raw = self.rfile.read(n)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:
            p = urlparse(self.path).path
            if p == "/api/summary":
                conn = sqlite3.connect(db_path)
                out = _query_counts(conn)
                conn.close()
                self._send_json({"ok": True, "data": out, "run": run_state.snapshot()})
                return
            if p == "/api/items":
                status, limit = self._parse_limit_status()
                conn = sqlite3.connect(db_path)
                out = _query_recent(conn, status=status, limit=limit)
                conn.close()
                self._send_json({"ok": True, "data": out})
                return
            if p == "/" or p == "/index.html":
                self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
                return
            if p == "/app.js":
                self._send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
                return
            if p == "/styles.css":
                self._send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def do_POST(self) -> None:
            p = urlparse(self.path).path.rstrip("/")
            if not p:
                p = "/"
            if p == "/api/run":
                body = self._body_json()
                mode = str(body.get("mode", "full"))
                if mode not in {"full", "collect", "deliver", "retry_deliver"}:
                    self._send_json({"ok": False, "error": "mode must be full|collect|deliver|retry_deliver"}, 400)
                    return
                if not run_state.start(mode):
                    self._send_json({"ok": False, "error": "pipeline is already running"}, 409)
                    return
                t = threading.Thread(target=_run_with_mode, args=(config_path, mode, run_state), daemon=True)
                t.start()
                self._send_json({"ok": True, "message": "started", "mode": mode}, 202)
                return

            if p.startswith("/api/ai/clean"):
                try:
                    body = self._body_json()
                    if not str(body.get("content", "")).strip():
                        self._send_json({"ok": False, "error": "content is required"}, 400)
                        return
                    cfg = load_config(config_path)
                    ai_result = _call_ai_webhook(cfg, body)
                    local_path = _save_local_article(cfg, ai_result)
                    github_result = _save_to_github(cfg, ai_result)
                    self._send_json(
                        {
                            "ok": True,
                            "data": ai_result,
                            "saved_local": local_path,
                            "saved_github": github_result,
                        }
                    )
                    return
                except Exception as ex:
                    self._send_json({"ok": False, "error": str(ex)}, 500)
                    return

            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def start_dashboard(config_path: str, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    cfg = load_config(config_path)
    db_path = cfg.get("state_db", "collector_state.sqlite3")
    init_db(db_path).close()
    run_state = RunState()
    handler = make_handler(config_path=config_path, db_path=db_path, run_state=run_state)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"[INFO] dashboard: http://{host}:{port}")
    if open_browser:
        url = f"http://{host}:{port}"
        threading.Thread(target=lambda: (time.sleep(0.4), webbrowser.open(url)), daemon=True).start()
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local dashboard for news pipeline.")
    parser.add_argument("--config", default="config.json", help="Path to config json.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--no-open-browser", action="store_true")
    args = parser.parse_args()
    start_dashboard(
        config_path=args.config,
        host=args.host,
        port=args.port,
        open_browser=not args.no_open_browser,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
