from typing import Any, Dict


def translate_item(item: Dict[str, Any], target_lang: str = "zh") -> Dict[str, Any]:
    """Reserved plugin hook. No-op for now."""
    _ = target_lang
    return item

