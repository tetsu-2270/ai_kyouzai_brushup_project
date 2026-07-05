import json

from src.canva_client import CanvaClient, write_canva_sync_report
from src.models import project_from_dict


def _project():
    return project_from_dict({
        "project_title": "テスト教材",
        "pages": [
            {"page_no": 1, "source_image": "a.png", "title": "P1", "summary": ""},
            {"page_no": 2, "source_image": "b.png", "title": "P2", "summary": ""},
        ],
    })


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_client_is_mock_when_api_key_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("CANVA_API_KEY", raising=False)
    client = CanvaClient(env_path=tmp_path / "no_such.env")
    assert client.is_mock is True


def test_mock_mode_never_calls_requests(tmp_path, monkeypatch):
    monkeypatch.delenv("CANVA_API_KEY", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("APIキー未設定時はrequestsを呼び出してはいけません")

    monkeypatch.setattr("src.canva_client.requests.post", fail_post)

    client = CanvaClient(env_path=tmp_path / "no_such.env")
    result = client.create_design_for_page(_project().pages[0])

    assert result.is_mock is True
    assert result.design_id == "mock-design-1"
    assert result.edit_url == "https://www.canva.com/design/mock-1/edit"


def test_client_reads_api_key_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CANVA_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("CANVA_API_KEY=dummy-key\n", encoding="utf-8")

    client = CanvaClient(env_path=env_file)

    assert client.is_mock is False
    assert client.api_key == "dummy-key"


def test_real_mode_calls_api_and_parses_result(monkeypatch):
    monkeypatch.setattr(
        "src.canva_client.requests.post",
        lambda *a, **k: _FakeResponse(
            {"design": {"id": "abc123", "urls": {"edit_url": "https://canva.example/edit"}}}
        ),
    )
    client = CanvaClient(api_key="dummy-key")
    result = client.create_design_for_page(_project().pages[0])

    assert result.is_mock is False
    assert result.design_id == "abc123"
    assert result.edit_url == "https://canva.example/edit"


def test_write_canva_sync_report_mock_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("CANVA_API_KEY", raising=False)
    output_path = tmp_path / "report.json"
    client = CanvaClient(env_path=tmp_path / "no_such.env")

    write_canva_sync_report(output_path, _project(), client=client)

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["mock"] is True
    assert "モック動作です" in report["note"]
    assert len(report["designs"]) == 2
    assert report["designs"][0]["design_id"] == "mock-design-1"


def test_write_canva_sync_report_prints_notice_when_mock(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CANVA_API_KEY", raising=False)
    output_path = tmp_path / "report.json"
    client = CanvaClient(env_path=tmp_path / "no_such.env")

    write_canva_sync_report(output_path, _project(), client=client)

    assert "CANVA_API_KEYが未設定" in capsys.readouterr().err
