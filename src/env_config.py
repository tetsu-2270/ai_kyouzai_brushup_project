from __future__ import annotations

import os
from pathlib import Path


def load_env_value(key: str, env_path: str | Path = ".env") -> str | None:
    value = os.environ.get(key)
    if value:
        return value

    env_file = Path(env_path)
    if not env_file.exists():
        return None

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip().strip('"').strip("'") or None

    return None
