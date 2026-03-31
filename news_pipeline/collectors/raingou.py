import hashlib
from typing import Any, Dict, List

from news_pipeline.http_client import HTTP
from news_pipeline.utils import hostname_from_url, utc_now_iso


def collect_raingou(source: Dict[str, Any], timeout_sec: int) -> List[Dict[str, Any]]:
    source_ids = source.get("source_ids", [])
    if not source_ids:
        return []

    base_url = source.get("base_url", "https://news.raingou.com/api/s")
    default_source_name = source.get("name", "raingou")
    out: List[Dict[str, Any]] = []
    fetched_at = utc_now_iso()

    for sid in source_ids:
        r = HTTP.get(base_url, params={"id": sid}, timeout=timeout_sec)
        r.raise_for_status()
        j = r.json()
        items = j.get("items", []) if isinstance(j, dict) else []
        source_name = f"{default_source_name}:{sid}"

        for row in items:
            url = str(row.get("url") or "")
            title = str(row.get("title") or "")
            rid = str(row.get("id") or "")
            id_basis = f"{sid}|{rid}|{url}|{title}"
            source_id = "raingou:" + hashlib.sha256(id_basis.encode("utf-8")).hexdigest()[:24]
            info = ""
            if isinstance(row.get("extra"), dict):
                info = str(row["extra"].get("info") or "")

            out.append(
                {
                    "source_id": source_id,
                    "source_name": source_name,
                    "title": title,
                    "url": url,
                    "domain": hostname_from_url(url),
                    "author": "",
                    "published_at": None,
                    "content_snippet": info,
                    "score": 0,
                    "raw": row,
                    "fetched_at": fetched_at,
                }
            )
    return out

