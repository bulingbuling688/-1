from typing import Any, Dict, List

from news_pipeline.collectors import collect_hn_topstories, collect_raingou, collect_rss


def collect_all(config: Dict[str, Any], timeout_sec: int) -> List[Dict[str, Any]]:
    all_items: List[Dict[str, Any]] = []
    for source in config.get("sources", []):
        if source.get("enabled", True) is False:
            continue
        stype = source.get("type")
        try:
            if stype == "hn_topstories":
                items = collect_hn_topstories(source, timeout_sec)
            elif stype == "rss":
                items = collect_rss(source, timeout_sec)
            elif stype == "raingou":
                items = collect_raingou(source, timeout_sec)
            else:
                print(f"[WARN] skip unknown source type: {stype}")
                continue
            print(f"[INFO] source={source.get('name', stype)} collected={len(items)}")
            all_items.extend(items)
        except Exception as ex:
            print(f"[ERROR] source={source.get('name', stype)} failed: {ex}")
    return all_items

