import datetime as dt
from urllib.parse import urlparse


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def hostname_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown-host"
    except Exception:
        return "unknown-host"

