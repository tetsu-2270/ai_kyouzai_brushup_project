from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

from .env_config import load_env_value
from .models import Page, Project

CANVA_API_BASE = "https://api.canva.com/rest/v1"


@dataclass
class CanvaDesignResult:
    page_no: int
    design_id: str
    edit_url: str
    is_mock: bool


class CanvaClient:
    """Canva Connect API (https://www.canva.com/developers/) のデザイン作成クライアント。

    CANVA_API_KEYが未設定の場合は実際のAPIを呼び出さず、モックの結果を返す。
    """

    def __init__(self, api_key: str | None = None, env_path: str | Path = ".env"):
        self.api_key = api_key if api_key is not None else load_env_value("CANVA_API_KEY", env_path)

    @property
    def is_mock(self) -> bool:
        return not self.api_key

    def create_design_for_page(self, page: Page) -> CanvaDesignResult:
        if self.is_mock:
            return CanvaDesignResult(
                page_no=page.page_no,
                design_id=f"mock-design-{page.page_no}",
                edit_url=f"https://www.canva.com/design/mock-{page.page_no}/edit",
                is_mock=True,
            )

        response = requests.post(
            f"{CANVA_API_BASE}/designs",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "design_type": {"type": "preset", "name": "InstagramStory"},
                "title": f"{page.title} (Page {page.page_no})",
            },
            timeout=30,
        )
        response.raise_for_status()
        design = response.json()["design"]
        return CanvaDesignResult(
            page_no=page.page_no,
            design_id=design["id"],
            edit_url=design["urls"]["edit_url"],
            is_mock=False,
        )

    def create_designs_for_project(self, project: Project) -> list[CanvaDesignResult]:
        return [self.create_design_for_page(page) for page in project.pages]


def write_canva_sync_report(path: str | Path, project: Project, client: CanvaClient | None = None) -> None:
    client = client or CanvaClient()

    if client.is_mock:
        print(
            "情報: CANVA_API_KEYが未設定のため、Canva連携はモック動作です"
            "（Canva APIは呼び出さず、仮のデザインIDを返します。任意機能のため未設定でも他の機能には影響しません）",
            file=sys.stderr,
        )

    results = client.create_designs_for_project(project)

    report = {
        "mock": client.is_mock,
        "note": (
            "CANVA_API_KEY未設定のためモック動作です。実際のCanvaデザインは作成されていません。"
            if client.is_mock
            else "Canva Connect APIを呼び出してデザインを作成しました。"
        ),
        "designs": [
            {"page_no": r.page_no, "design_id": r.design_id, "edit_url": r.edit_url}
            for r in results
        ],
    }

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
