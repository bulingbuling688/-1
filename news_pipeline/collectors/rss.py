import hashlib
from typing import Any, Dict, List

import feedparser

from news_pipeline.utils import hostname_from_url, utc_now_iso


def collect_rss(source: Dict[str, Any], timeout_sec: int) -> List[Dict[str, Any]]:
    del timeout_sec  # feedparser does not use requests timeout directly
    url = source["url"]
    limit = int(source.get("limit", 20))
    name = source.get("name", hostname_from_url(url))
    fetched_at = utc_now_iso()

    feed = feedparser.parse(url)
    out: List[Dict[str, Any]] = []
    for e in feed.entries[:limit]:
        link = getattr(e, "link", "") or ""
        title = getattr(e, "title", "") or ""
        author = getattr(e, "author", "") or ""
        published_at = (
            getattr(e, "published", None)
            or getattr(e, "updated", None)
            or getattr(e, "published_parsed", None)
            or None
        )
        snippet = getattr(e, "summary", "") or ""

        sid_basis = f"{name}|{link}|{title}"
        source_id = "rss:" + hashlib.sha256(sid_basis.encode("utf-8")).hexdigest()[:24]

        out.append(
            {
                "source_id": source_id,
                "source_name": name,
                "title": title,
                "url": link,
                "domain": hostname_from_url(link),
                "author": author,
                "published_at": str(published_at) if published_at else None,
                "content_snippet": snippet,
                "score": 0,
                "raw": {
                    "title": title,
                    "link": link,
                    "author": author,
                    "published": str(published_at) if published_at else None,
                },
                "fetched_at": fetched_at,
            }
        )
    return out

