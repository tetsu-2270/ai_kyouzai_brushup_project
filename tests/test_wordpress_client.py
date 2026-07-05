import json

import pytest

from src.models import project_from_dict
from src.wordpress_client import WordPressClient, write_wordpress_publish_report


def _project():
    return project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "title": "P1",
                "summary": "概要",
                "lines": [{"speaker": "まじょこ", "text": "こんにちは"}],
                "improvement_points": ["改善点1"],
            }
        ],
    })


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _clear_wp_env(monkeypatch):
    for key in ("WP_URL", "WP_USERNAME", "WP_APP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


def test_client_is_mock_when_credentials_missing(tmp_path, monkeypatch):
    _clear_wp_env(monkeypatch)
    client = WordPressClient(env_path=tmp_path / "no_such.env")
    assert client.is_mock is True


def test_client_is_mock_when_partially_configured(tmp_path, monkeypatch):
    _clear_wp_env(monkeypatch)
    client = WordPressClient(base_url="https://example.com", env_path=tmp_path / "no_such.env")
    assert client.is_mock is True


def test_mock_mode_never_calls_requests(tmp_path, monkeypatch):
    _clear_wp_env(monkeypatch)

    def fail(*args, **kwargs):
        raise AssertionError("認証情報未設定時はrequestsを呼び出してはいけません")

    monkeypatch.setattr("src.wordpress_client.requests.post", fail)
    monkeypatch.setattr("src.wordpress_client.requests.get", fail)

    client = WordPressClient(env_path=tmp_path / "no_such.env")
    result = client.publish_project(_project(), category_names=["お知らせ"], tag_names=["まじょこ"])

    assert result.is_mock is True
    assert len(result.media_ids) == 1
    assert result.featured_media_id == result.media_ids[0]
    assert len(result.category_ids) == 1
    assert len(result.tag_ids) == 1
    assert result.post_url.startswith("https://example.com/mock-post/")


def test_client_reads_credentials_from_env_file(tmp_path, monkeypatch):
    _clear_wp_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "WP_URL=https://example.com\nWP_USERNAME=admin\nWP_APP_PASSWORD=secret\n",
        encoding="utf-8",
    )

    client = WordPressClient(env_path=env_file)

    assert client.is_mock is False
    assert client.base_url == "https://example.com"


def test_real_mode_skips_missing_image_file(monkeypatch):
    monkeypatch.setattr(
        "src.wordpress_client.requests.get",
        lambda *a, **k: _FakeResponse([]),
    )

    created = {"categories": 0, "tags": 0}

    def fake_post(url, **kwargs):
        if url.endswith("/categories"):
            created["categories"] += 1
            return _FakeResponse({"id": 10, "name": "お知らせ"})
        if url.endswith("/tags"):
            created["tags"] += 1
            return _FakeResponse({"id": 20, "name": "まじょこ"})
        if url.endswith("/posts"):
            return _FakeResponse({"id": 100, "link": "https://example.com/?p=100"})
        raise AssertionError(f"unexpected POST to {url}")

    monkeypatch.setattr("src.wordpress_client.requests.post", fake_post)

    client = WordPressClient(base_url="https://example.com", username="admin", app_password="secret")
    result = client.publish_project(
        _project(),
        image_dir="no_such_dir",
        category_names=["お知らせ"],
        tag_names=["まじょこ"],
    )

    assert result.is_mock is False
    assert result.media_ids == []
    assert result.featured_media_id is None
    assert result.skipped_images == ["a.png"]
    assert result.category_ids == [10]
    assert result.tag_ids == [20]
    assert result.post_id == 100


def test_invalid_status_raises_clear_error(tmp_path, monkeypatch):
    _clear_wp_env(monkeypatch)
    client = WordPressClient(env_path=tmp_path / "no_such.env")

    with pytest.raises(ValueError, match="statusは"):
        client.publish_project(_project(), status="deleted")


def test_write_wordpress_publish_report_mock_mode(tmp_path, monkeypatch):
    _clear_wp_env(monkeypatch)
    output_path = tmp_path / "report.json"
    client = WordPressClient(env_path=tmp_path / "no_such.env")

    write_wordpress_publish_report(output_path, _project(), client=client)

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["mock"] is True
    assert "モック動作です" in report["note"]
    assert "post_url" in report


def test_write_wordpress_publish_report_prints_notice_when_mock(tmp_path, monkeypatch, capsys):
    _clear_wp_env(monkeypatch)
    output_path = tmp_path / "report.json"
    client = WordPressClient(env_path=tmp_path / "no_such.env")

    write_wordpress_publish_report(output_path, _project(), client=client)

    assert "WP_URL/WP_USERNAME/WP_APP_PASSWORD" in capsys.readouterr().err
