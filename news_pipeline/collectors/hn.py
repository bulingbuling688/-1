import datetime as dt
from typing import Any, Dict, List

from news_pipeline.http_client import HTTP
from news_pipeline.utils import hostname_from_url, utc_now_iso


def collect_hn_topstories(source: Dict[str, Any], timeout_sec: int) -> List[Dict[str, Any]]:
    limit = int(source.get("limit", 20))
    name = source.get("name", "hackernews")
    top_url = source.get("topstories_url", "https://hacker-news.firebaseio.com/v0/topstories.json")
    item_url_tpl = source.get("item_url_template", "https://hacker-news.firebaseio.com/v0/item/{id}.json")

    resp = HTTP.get(top_url, timeout=timeout_sec)
    resp.raise_for_status()
    ids = resp.json()[:limit]

    out: List[Dict[str, Any]] = []
    fetched_at = utc_now_iso()
    for sid in ids:
        r = HTTP.get(item_url_tpl.format(id=sid), timeout=timeout_sec)
        r.raise_for_status()
        j = r.json()
        if not isinstance(j, dict):
            continue

        url = j.get("url") or f"https://news.ycombinator.com/item?id={j.get('id')}"
        published_ts = j.get("time")
        published_at = (
            dt.datetime.fromtimestamp(published_ts, tz=dt.timezone.utc).isoformat()
            if isinstance(published_ts, (int, float))
            else None
        )

        out.append(
            {
                "source_id": f"hn:{j.get('id')}",
                "source_name": name,
                "title": j.get("title") or "",
                "url": url,
                "domain": hostname_from_url(url),
                "author": j.get("by") or "",
                "published_at": published_at,
                "content_snippet": j.get("text") or "",
                "score": int(j.get("score") or 0),
                "raw": j,
                "fetched_at": fetched_at,
            }
        )
    return out

