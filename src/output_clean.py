from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

# build-all/import-source/review-report/ocr-check/llm-handoffが生成する既知の成果物のみを
# 削除対象にする。ここに無いパス（output-dir配下の手動ファイル・他コマンドの生成物）には
# 一切触れない。ページ数が前回より減った場合に、古いページの画像等が混在するのを防ぐための
# --clean-output専用のクリーンアップ対象一覧。
KNOWN_OUTPUT_DIRS = (
    "assets",
    "editable",
    "compat",
    "scenario",
    "rendered",
    "exports",
    "canva",
)
KNOWN_OUTPUT_FILES = (
    "imported_pages.json",
    "review_report.md",
    "ocr_check_report.md",
    "ocr_correction_candidates.json",
    "llm_handoff.md",
    # Phase 8時点のbuild-allが output_dir 直下に直接生成していた旧仕様の完成output。
    # Phase 9で output/compat/ 配下にまとめられ役割が重複したため、現行のbuild-allはもう
    # ここには生成しない（詳細はcli.pyのbuild_all()docstring参照）。旧バージョンの実行結果や
    # 手作業での個別コマンド実行（generate/canva/docx/pdf）が output_dir 直下に残っていると、
    # output/compat/配下の現行版と紛らわしく誤参照の原因になるため、既知の生成物として削除対象にする。
    "lesson_pages.json",
    "canva_design.md",
    "brushup.md",
    "brushup.docx",
    "brushup.pdf",
)

# output-dirにこれらのディレクトリ自体を指定された場合、または削除対象パスの実体（symlink解決後）
# がこれらと重なる場合は、絶対に削除しない。
_PROTECTED_DIR_NAMES = ("input", ".git", "src", "tests", "docs")


class UnsafeOutputDirError(ValueError):
    """--clean-outputの削除対象として安全と判断できないoutput-dirが指定された場合に送出する。"""


def resolve_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _is_within(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False


def _allowed_tmp_roots() -> tuple[Path, ...]:
    """安全とみなす一時ディレクトリのルート一覧。

    `/tmp`に加えて`tempfile.gettempdir()`も含める。macOSでは`/tmp`が`/private/tmp`への
    symlinkである一方、Pythonの一時ディレクトリ既定値（`pytest`の`tmp_path`が使うものと同じ）は
    `/private/var/folders/.../T`のようにこれとは別系統になるため、「/tmp配下」だけでは
    OS標準の一時ディレクトリを取りこぼす。どちらもOSが管理する使い捨ての一時領域という点で
    安全性の意味は同じであるため、両方を許可対象とする。
    """
    roots = {Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve()}
    return tuple(roots)


def _is_within_any(path: Path, ancestors: tuple[Path, ...]) -> bool:
    return any(path == ancestor or _is_within(path, ancestor) for ancestor in ancestors)


def validate_clean_output_dir(output_dir: str | Path, project_root: Path | None = None) -> Path:
    """--clean-outputで削除対象にしてよいoutput-dirかどうかを検証し、解決済み絶対パスを返す。

    安全条件を満たさない場合は削除を一切行わずUnsafeOutputDirErrorを送出する。
    - 空文字・ファイルシステムルート・ホームディレクトリ・プロジェクトルートそのものは拒否
    - プロジェクトディレクトリ配下、または/tmp配下であることを要求
    - input/・.git/・src/・tests/・docs/と重なる場合は拒否
    """
    if project_root is None:
        project_root = resolve_project_root()
    project_root = project_root.resolve()

    raw = str(output_dir).strip()
    if not raw:
        raise UnsafeOutputDirError("--output-dirが空です。output-dirのクリーンアップは実行できません。")

    resolved = Path(output_dir).expanduser().resolve()

    if resolved == Path(resolved.anchor):
        raise UnsafeOutputDirError(f"output-dirがファイルシステムルートです: {resolved}")
    if resolved == Path.home().resolve():
        raise UnsafeOutputDirError(f"output-dirがホームディレクトリです: {resolved}")
    if resolved == project_root:
        raise UnsafeOutputDirError(f"output-dirがプロジェクトルートそのものです: {resolved}")

    if not (_is_within(resolved, project_root) or _is_within_any(resolved, _allowed_tmp_roots())):
        raise UnsafeOutputDirError(
            f"output-dirはプロジェクトディレクトリ配下または/tmp配下である必要があります: {resolved}"
        )

    for name in _PROTECTED_DIR_NAMES:
        protected = (project_root / name).resolve()
        if resolved == protected or _is_within(protected, resolved):
            raise UnsafeOutputDirError(
                f"output-dirが保護対象ディレクトリ（{name}）と重なっています: {resolved}"
            )

    return resolved


def _is_safe_target(path: Path, project_root: Path) -> bool:
    """削除対象1件ごとの最終安全確認。symlink経由でプロジェクト外・保護ディレクトリを
    指していないかを、実体解決後のパスで再チェックする。
    """
    try:
        real = path.resolve()
    except OSError:
        return False

    if not (_is_within(real, project_root) or _is_within_any(real, _allowed_tmp_roots())):
        return False

    for name in _PROTECTED_DIR_NAMES:
        protected = (project_root / name).resolve()
        if real == protected or _is_within(protected, real):
            return False
    return True


def clean_known_outputs(output_dir: str | Path, project_root: Path | None = None) -> dict[str, list[str]]:
    """output-dir配下の、build-all/import-source/review-report/ocr-check/llm-handoffが生成する
    既知の成果物だけを削除する。output-dir配下にある未知の手動ファイル・ディレクトリには触れない。

    削除対象が存在しない場合はエラーにせずスキップする。戻り値は
    {"removed": [削除したパス], "skipped": [存在しなかった・安全確認で除外したパス]}。
    """
    if project_root is None:
        project_root = resolve_project_root()
    project_root = project_root.resolve()

    resolved_output_dir = validate_clean_output_dir(output_dir, project_root=project_root)

    removed: list[str] = []
    skipped: list[str] = []

    for name in KNOWN_OUTPUT_DIRS:
        target = resolved_output_dir / name
        if not target.exists():
            skipped.append(str(target))
            continue
        if not _is_safe_target(target, project_root):
            skipped.append(str(target))
            continue
        shutil.rmtree(target)
        removed.append(str(target))

    for name in KNOWN_OUTPUT_FILES:
        target = resolved_output_dir / name
        if not target.exists():
            skipped.append(str(target))
            continue
        if not _is_safe_target(target, project_root):
            skipped.append(str(target))
            continue
        target.unlink()
        removed.append(str(target))

    return {"removed": removed, "skipped": skipped}
