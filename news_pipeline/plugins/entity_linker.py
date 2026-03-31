from typing import Any, Dict, List


def extract_entities(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Reserved plugin hook. No-op for now."""
    _ = item
    return []

