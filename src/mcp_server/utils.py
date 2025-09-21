from __future__ import annotations
from dataclasses import asdict, is_dataclass
from typing import Any

def to_serializable(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: to_serializable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_serializable(x) for x in obj]
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            pass
    return obj
