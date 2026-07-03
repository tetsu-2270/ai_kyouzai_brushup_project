import json
from pathlib import Path

from .models import Project, project_from_dict


def load_project(path: str | Path) -> Project:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    try:
        text = input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(
            f"入力ファイルがUTF-8として読み込めません: {input_path} ({e})"
        ) from e

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"入力ファイルのJSONが不正です: {input_path} "
            f"({e.lineno}行目 {e.colno}列目: {e.msg})"
        ) from e

    return project_from_dict(data)
