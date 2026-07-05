from __future__ import annotations

import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

from .env_config import load_env_value
from .models import Project

WP_API_TIMEOUT = 30
ALLOWED_POST_STATUSES = {"draft", "publish", "future", "pending", "private"}


@dataclass
class WordPressPublishResult:
    post_id: int
    post_url: str
    featured_media_id: int | None
    media_ids: list[int]
    category_ids: list[int]
    tag_ids: list[int]
    skipped_images: list[str]
    is_mock: bool


def _build_post_html(project: Project) -> str:
    parts = [f"<p>対象読者: {html.escape(project.target_reader)}</p>"]
    for page in project.pages:
        parts.append(f"<h2>Page {page.page_no}: {html.escape(page.title)}</h2>")
        parts.append(f"<p>{html.escape(page.summary or '未設定')}</p>")
        if page.lines:
            items = "".join(
                f"<li><strong>{html.escape(item.speaker)}</strong>: {html.escape(item.text)}</li>"
                for item in page.lines
            )
            parts.append(f"<ul>{items}</ul>")
        if page.improvement_points:
            items = "".join(f"<li>{html.escape(point)}</li>" for point in page.improvement_points)
            parts.append(f"<h3>改善ポイント</h3><ul>{items}</ul>")
    return "\n".join(parts)


class WordPressClient:
    """WordPress REST API (wp-json/wp/v2) クライアント。

    WP_URL/WP_USERNAME/WP_APP_PASSWORDのいずれかが未設定の場合は
    実際のAPIを呼び出さず、モックの結果を返す。
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
        env_path: str | Path = ".env",
    ):
        self.base_url = (base_url if base_url is not None else load_env_value("WP_URL", env_path) or "").rstrip("/")
        self.username = username if username is not None else load_env_value("WP_USERNAME", env_path)
        self.app_password = (
            app_password if app_password is not None else load_env_value("WP_APP_PASSWORD", env_path)
        )
        self._mock_counter = 0

    @property
    def is_mock(self) -> bool:
        return not (self.base_url and self.username and self.app_password)

    def _auth(self) -> tuple[str, str]:
        return (self.username, self.app_password)

    def _next_mock_id(self) -> int:
        self._mock_counter += 1
        return 9000 + self._mock_counter

    def upload_image(self, image_path: str | Path) -> dict:
        image_path = Path(image_path)
        if self.is_mock:
            return {"id": self._next_mock_id(), "source_url": f"https://example.com/mock-media/{image_path.name}"}

        response = requests.post(
            f"{self.base_url}/wp-json/wp/v2/media",
            auth=self._auth(),
            headers={"Content-Disposition": f'attachment; filename="{image_path.name}"'},
            data=image_path.read_bytes(),
            timeout=WP_API_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return {"id": data["id"], "source_url": data.get("source_url", "")}

    def _get_or_create_term(self, endpoint: str, name: str) -> int:
        if self.is_mock:
            return self._next_mock_id()

        search_response = requests.get(
            f"{self.base_url}/wp-json/wp/v2/{endpoint}",
            auth=self._auth(),
            params={"search": name},
            timeout=WP_API_TIMEOUT,
        )
        search_response.raise_for_status()
        for item in search_response.json():
            if item["name"] == name:
                return item["id"]

        create_response = requests.post(
            f"{self.base_url}/wp-json/wp/v2/{endpoint}",
            auth=self._auth(),
            json={"name": name},
            timeout=WP_API_TIMEOUT,
        )
        create_response.raise_for_status()
        return create_response.json()["id"]

    def get_or_create_category(self, name: str) -> int:
        return self._get_or_create_term("categories", name)

    def get_or_create_tag(self, name: str) -> int:
        return self._get_or_create_term("tags", name)

    def create_post(
        self,
        title: str,
        content: str,
        category_ids: list[int],
        tag_ids: list[int],
        featured_media_id: int | None,
        status: str = "draft",
    ) -> dict:
        if self.is_mock:
            post_id = self._next_mock_id()
            return {"id": post_id, "link": f"https://example.com/mock-post/{post_id}"}

        payload = {
            "title": title,
            "content": content,
            "status": status,
            "categories": category_ids,
            "tags": tag_ids,
        }
        if featured_media_id is not None:
            payload["featured_media"] = featured_media_id

        response = requests.post(
            f"{self.base_url}/wp-json/wp/v2/posts",
            auth=self._auth(),
            json=payload,
            timeout=WP_API_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return {"id": data["id"], "link": data.get("link", "")}

    def publish_project(
        self,
        project: Project,
        image_dir: str | Path = "input/raw_images",
        category_names: list[str] | None = None,
        tag_names: list[str] | None = None,
        status: str = "draft",
    ) -> WordPressPublishResult:
        if status not in ALLOWED_POST_STATUSES:
            raise ValueError(
                f"statusは{sorted(ALLOWED_POST_STATUSES)}のいずれかを指定してください: {status!r}"
            )

        category_names = category_names or []
        tag_names = tag_names or []
        image_root = Path(image_dir)

        media_ids: list[int] = []
        skipped_images: list[str] = []
        for page in project.pages:
            if not page.source_image:
                continue
            image_path = image_root / page.source_image
            if self.is_mock or image_path.exists():
                media = self.upload_image(image_path)
                media_ids.append(media["id"])
            else:
                skipped_images.append(page.source_image)

        category_ids = [self.get_or_create_category(name) for name in category_names]
        tag_ids = [self.get_or_create_tag(name) for name in tag_names]
        featured_media_id = media_ids[0] if media_ids else None

        post = self.create_post(
            title=project.project_title,
            content=_build_post_html(project),
            category_ids=category_ids,
            tag_ids=tag_ids,
            featured_media_id=featured_media_id,
            status=status,
        )

        return WordPressPublishResult(
            post_id=post["id"],
            post_url=post["link"],
            featured_media_id=featured_media_id,
            media_ids=media_ids,
            category_ids=category_ids,
            tag_ids=tag_ids,
            skipped_images=skipped_images,
            is_mock=self.is_mock,
        )


def write_wordpress_publish_report(
    path: str | Path,
    project: Project,
    client: WordPressClient | None = None,
    image_dir: str | Path = "input/raw_images",
    category_names: list[str] | None = None,
    tag_names: list[str] | None = None,
    status: str = "draft",
) -> None:
    client = client or WordPressClient()

    if client.is_mock:
        print(
            "情報: WP_URL/WP_USERNAME/WP_APP_PASSWORDのいずれかが未設定のため、WordPress連携はモック動作です"
            "（WordPress REST APIは呼び出さず、仮のID・URLを返します。任意機能のため未設定でも他の機能には影響しません）",
            file=sys.stderr,
        )

    result = client.publish_project(
        project,
        image_dir=image_dir,
        category_names=category_names,
        tag_names=tag_names,
        status=status,
    )

    report = {
        "mock": result.is_mock,
        "note": (
            "WP_URL/WP_USERNAME/WP_APP_PASSWORD未設定のためモック動作です。実際のWordPress記事は作成されていません。"
            if result.is_mock
            else "WordPress REST APIを呼び出して記事を作成しました。"
        ),
        "post_id": result.post_id,
        "post_url": result.post_url,
        "featured_media_id": result.featured_media_id,
        "media_ids": result.media_ids,
        "category_ids": result.category_ids,
        "tag_ids": result.tag_ids,
        "skipped_images": result.skipped_images,
    }

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
