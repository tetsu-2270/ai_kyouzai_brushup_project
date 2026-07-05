import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "make_release_zip.sh"


def _build_fake_repo(tmp_path: Path) -> Path:
    """input/・output/にダミーファイルを含む最小構成の疑似リポジトリをtmp_path配下に作る。

    実リポジトリのinput//output/を直接操作せず、scripts/make_release_zip.sh自体を
    疑似リポジトリへコピーして実行することで、実データに触れずに除外挙動を検証する。
    """
    repo = tmp_path / "fake_repo"

    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)
    script_copy = scripts_dir / "make_release_zip.sh"
    script_copy.write_text(_SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    script_copy.chmod(0o755)

    (repo / "input").mkdir()
    (repo / "input" / "dummy_source.json").write_text("{}", encoding="utf-8")

    (repo / "output").mkdir()
    (repo / "output" / "dummy_lesson_pages.json").write_text("{}", encoding="utf-8")

    (repo / "src").mkdir()
    (repo / "src" / "dummy.py").write_text("# dummy\n", encoding="utf-8")

    (repo / "README.md").write_text("# fake repo\n", encoding="utf-8")

    return repo


@pytest.mark.skipif(shutil.which("zip") is None, reason="zipコマンドが無い環境ではスキップ")
def test_make_release_zip_excludes_input_and_output_contents(tmp_path):
    repo = _build_fake_repo(tmp_path)
    output_zip = tmp_path / "release.zip"

    result = subprocess.run(
        ["bash", str(repo / "scripts" / "make_release_zip.sh"), str(output_zip)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    assert output_zip.exists()
    with zipfile.ZipFile(output_zip) as zf:
        names = zf.namelist()

    # ディレクトリの空エントリ自体("input/"などのマーカー)が入るかはzip実装依存のため許容し、
    # input//output/配下に実ファイルが1つも含まれないことだけを検証する。
    leaked = [
        name for name in names
        if (name.startswith("input/") or name.startswith("output/")) and name not in ("input/", "output/")
    ]
    assert leaked == []


@pytest.mark.skipif(shutil.which("zip") is None, reason="zipコマンドが無い環境ではスキップ")
def test_make_release_zip_still_includes_other_files(tmp_path):
    repo = _build_fake_repo(tmp_path)
    output_zip = tmp_path / "release.zip"

    subprocess.run(
        ["bash", str(repo / "scripts" / "make_release_zip.sh"), str(output_zip)],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    with zipfile.ZipFile(output_zip) as zf:
        names = zf.namelist()

    assert "README.md" in names
    assert "src/dummy.py" in names
