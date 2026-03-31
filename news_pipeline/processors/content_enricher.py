import time
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from news_pipeline.http_client import HTTP


def extract_text_from_html(html: str, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    article = soup.find("article")
    scope = article if article is not None else soup

    parts: List[str] = []
    for p in scope.find_all("p"):
        t = p.get_text(" ", strip=True)
        if t:
            parts.append(t)
    text = "\n".join(parts).strip()
    if not text:
        text = soup.get_text(" ", strip=True)
    return text[:max_chars]


def enrich_content(items: List[Dict[str, Any]], config: Dict[str, Any]) -> None:
    content_cfg = config.get("content_fetch", {})
    if not content_cfg.get("enabled", False):
        return

    timeout_sec = int(content_cfg.get("timeout_sec", 12))
    max_chars = int(content_cfg.get("max_chars", 6000))
    ua = content_cfg.get("user_agent", "Mozilla/5.0 (NewsCollector)")
    headers = {"User-Agent": ua}

    for idx, item in enumerate(items, start=1):
        url = item.get("url") or ""
        if not url.startswith("http"):
            continue
        try:
            r = HTTP.get(url, timeout=timeout_sec, headers=headers)
            if 200 <= r.status_code < 300 and "text/html" in (r.headers.get("content-type") or ""):
                text = extract_text_from_html(r.text, max_chars=max_chars)
                if text:
                    item["content_full"] = text
                    if not item.get("content_snippet"):
                        item["content_snippet"] = text[:400]
            time.sleep(0.15)
        except Exception:
            pass
        if idx % 20 == 0:
            print(f"[INFO] content_enriched={idx}/{len(items)}")

