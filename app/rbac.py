"""Role-based Access Control helper functions."""

import json
from pathlib import Path
from typing import List

from app.config import settings

_ACCESS_CONTROL_CACHE = None


def _load_access_control():
    global _ACCESS_CONTROL_CACHE
    if _ACCESS_CONTROL_CACHE is None:
        ac_path = Path(settings.DATA_DIR) / "access_control.json"
        if not ac_path.exists():
            # Fallback path if run from different cwd
            ac_path = Path("./data/access_control.json")
        with open(ac_path, "r", encoding="utf-8") as f:
            _ACCESS_CONTROL_CACHE = json.load(f)
    return _ACCESS_CONTROL_CACHE


def allowed_levels(role: str) -> List[str]:
    """Return list of allowed access levels for a given role.
    
    Default deny: unknown role returns an empty list.
    """
    if not role:
        return []
    
    ac_data = _load_access_control()
    roles_map = ac_data.get("roles", {})
    return roles_map.get(role.strip().lower(), [])
