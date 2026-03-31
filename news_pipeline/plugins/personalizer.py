from typing import Any, Dict, List


def apply_personalization(items: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Reserved plugin hook. No-op for now."""
    _ = profile
    return items

