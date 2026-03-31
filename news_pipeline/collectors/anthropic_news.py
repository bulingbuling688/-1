import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from news_pipeline.http_client import HTTP
from news_pipeline.utils import hostname_from_url, utc_now_iso


_DATE_PAT = re.compile(r"\b([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\b")


def _parse_date_from_text(text: str) -> str | None:
    m = _DATE_PAT.search(text or "")
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1), "%b %d, %Y").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def collect_anthropic_news(source: Dict[str, Any], timeout_sec: int) -> List[Dict[str, Any]]:
    page_url = source.get("url", "https://www.anthropic.com/news")
    limit = int(source.get("limit", 20))
    name = source.get("name", "anthropic_news")
    fetched_at = utc_now_iso()

    r = HTTP.get(page_url, timeout=timeout_sec)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    out: List[Dict[str, Any]] = []
    seen_links = set()

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "")
        if not href.startswith("/news/") or href == "/news/":
            continue
        url = urljoin(page_url, href)
        if url in seen_links:
            continue

        text = a.get_text(" ", strip=True)
        if not text:
            continue

        source_id = "anthropic:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        published_at = _parse_date_from_text(text)

        out.append(
            {
                "source_id": source_id,
                "source_name": name,
                "title": text[:300],
                "url": url,
                "domain": hostname_from_url(url),
                "author": "Anthropic",
                "published_at": published_at,
                "content_snippet": text[:800],
                "score": 0,
                "raw": {"href": href, "text": text},
                "fetched_at": fetched_at,
            }
        )
        seen_links.add(url)
        if len(out) >= limit:
            break

    return out
