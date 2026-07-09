from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .canva_client import write_canva_sync_report
from .canva_renderer import render_canva_design
from .docx_renderer import write_docx
from .execution_logger import ExecutionLogger, TeeStderr
from .image_renderer import render_document_images
from .import_source import import_source
from .lesson_pages import LessonDocument, build_lesson_pages, render_review_report, write_lesson_pages_json
from .edit_plan import render_edit_plan_template_markdown
from .llm_handoff import render_llm_handoff_markdown
from .llm_suggestions import (
    build_llm_suggestion_candidates,
    load_llm_suggestions_markdown,
    parse_llm_suggestions,
    render_llm_suggestion_report_markdown,
    write_llm_suggestion_candidates_json,
)
from .ocr_apply import (
    apply_ocr_corrections,
    load_correction_candidates,
    render_ocr_apply_report_markdown,
    write_lesson_pages,
)
from .ocr_check import (
    build_ocr_correction_candidates,
    render_ocr_check_report_markdown,
    write_correction_candidates_json,
)
from .ocr_patterns import load_ocr_patterns
from .ocr_environment import (
    OCR_REQUIRED_MODES,
    format_environment_report,
    format_ocr_required_all_pages_empty_error,
    format_ocr_required_japanese_missing_error,
    format_ocr_required_tesseract_missing_error,
    format_partial_pages_empty_warning,
    get_ocr_environment_status,
)
from .parser import load_lesson_document, load_project
from .pdf_renderer import write_pdf
from .pptx_export_renderer import write_pptx_export
from .renderer import render_brushup
from .scenario_renderer import write_scenario_outputs
from .wordpress_client import write_wordpress_publish_report

# 完成outputの形式。「same」はinputの性質(画像/PDF/PPTX)に合わせて自動選択する。
OUTPUT_FORMAT_CHOICES = ["same", "image", "pdf", "pptx", "docx", "md", "canva", "json", "all"]

_INPUT_KIND_TO_DEFAULT_FORMAT = {"image": "image", "pdf": "pdf", "pptx": "pptx"}

# exports/canva配下の完成outputファイル名。プロジェクトタイトルが日本語・記号を含み得るため、
# ファイルシステム非依存の固定名にする（内容はlesson_pages.jsonのproject_titleを引き続き含む）。
_EXPORT_BASENAME = "material"


def write_text(path: str | Path, text: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def run_import_source(
    input_path: str, output_path: str | Path, assets_dir: str | Path | None = None, quiet: bool = False
) -> dict[str, object]:
    """元資料(画像/PDF/PPTX)からimported_pages.json互換のJSONを生成して書き出す。

    戻り値の辞書（pages形式互換）は、build_all()がOCR前提チェックに使う。

    `quiet=True`は画像取り込み時のOCR関連警告を抑制する（`build_all()`がOCR必須モードで
    自前の集約済みエラー/警告を表示する場合に、`import_source()`側の重複表示を避けるため。
    Phase 10.2追加修正）。単体の`import-source`コマンドからは指定しない（既定False、
    従来どおりここで警告を表示する）。
    """
    output_path = Path(output_path)
    resolved_assets_dir = Path(assets_dir) if assets_dir else output_path.parent / "assets"
    imported = import_source(input_path, resolved_assets_dir, quiet=quiet)
    write_text(output_path, json.dumps(imported, ensure_ascii=False, indent=2) + "\n")
    return imported


def _detect_input_kind(input_path: str) -> str:
    """元資料のパスから種別(image/pdf/pptx)を判定する（--output-format same の解決に使う）。"""
    path = Path(input_path)
    if path.is_dir():
        return "image"
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".pptx":
        return "pptx"
    return "image"


def resolve_output_format(output_format: str, input_kind: str) -> str:
    """--output-format same を、入力の性質に応じた具体的な形式に解決する。"""
    if output_format == "same":
        return _INPUT_KIND_TO_DEFAULT_FORMAT.get(input_kind, "image")
    return output_format


def validate_generated_file(path: str | Path, label: str) -> None:
    """成果物ファイルが実際に生成された（存在し、サイズが0でない）ことを検証する。

    レンダラーが例外を投げずに空成果物だけ生成してしまう、あるいは処理の途中で書き込みが
    スキップされてしまうようなケースを、正常終了扱いにしないための安全網（Phase 10.2追加修正）。
    """
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"{label}の成果物が生成されませんでした: {file_path}")
    if file_path.stat().st_size == 0:
        raise ValueError(f"{label}の成果物が空です: {file_path}")


def validate_generated_json_pages(path: str | Path, pages_count: int, label: str) -> None:
    """JSON成果物（imported_pages.json/lesson_pages.json等）について、ファイル自体の生成に
    加え、取り込み・生成したpagesが0件でないことを検証する。

    OCR自体の成否（各ページのlinesが空かどうか）は別の関心事であり、既存方針（`import-source`
    単体では警告のうえ継続）に従う。ここで検証するのはあくまで「pagesの件数」であり、
    「OCRでテキストが取れたか」ではない。
    """
    validate_generated_file(path, label)
    if pages_count == 0:
        raise ValueError(f"{label}の処理結果にページがありません: {path}")


def _expected_output_paths(output_dir: Path, resolved_format: str) -> list[Path]:
    """指定されたoutput-formatについて、生成されているべき成果物パス（画像を除く）の一覧を返す
    （`_verify_expected_outputs()`が「指定した形式の成果物が実際に生成されたか」を検証するのに使う）。
    画像（`rendered/`）は`render_document_images()`が返す実ファイルパスの一覧で別途検証するため、
    ここには含めない（Phase 10.2追加修正: ディレクトリの存在だけで「画像あり」とみなさないため）。
    「json」はeditable中間ファイル自体が対象であり、別工程で既に生成されているためここでは対象外。
    """
    mapping: dict[str, list[Path]] = {
        "image": [],
        "pdf": [output_dir / "exports" / f"{_EXPORT_BASENAME}.pdf"],
        "pptx": [output_dir / "exports" / f"{_EXPORT_BASENAME}.pptx"],
        "docx": [output_dir / "exports" / f"{_EXPORT_BASENAME}.docx"],
        "md": [output_dir / "exports" / f"{_EXPORT_BASENAME}.md"],
        "canva": [output_dir / "canva" / "canva_design.md"],
        "json": [],
    }
    if resolved_format == "all":
        paths: list[Path] = []
        for fmt in ("image", "pdf", "pptx", "docx", "md", "canva"):
            paths.extend(mapping[fmt])
        return paths
    return mapping.get(resolved_format, [])


def _verify_expected_images(
    resolved_format: str, expected_page_count: int, image_paths: list[Path]
) -> None:
    """画像output（`rendered/page_NNN.png`）が期待される場合に、実際に生成された画像ファイルの
    パス一覧（`render_document_images()`の戻り値）を検証する。

    `output/rendered/`ディレクトリの存在や非空判定だけでは、前回実行時の古い画像ファイルが
    残っているだけでも「成功」とみなしてしまう（今回実行で1枚も生成されていなくても検知できない）
    ため、今回の実行が実際に書き出したファイルパスそのものを検証する（Phase 10.2追加修正）。
    """
    if resolved_format not in ("image", "pptx", "all"):
        return
    # pptx単体はrendered/自体を正式outputとして公開しないため、画像0枚は許容しない対象外とする
    # （PPTXがrendered画像を内部的に使うのはimage_paths経由であり、rendered/への露出義務は無い）。
    if resolved_format == "pptx":
        return

    if not image_paths:
        raise ValueError(
            "画像output(rendered/)が生成されませんでした（imported_pages/pagesは存在します）。"
        )
    if expected_page_count and len(image_paths) != expected_page_count:
        raise ValueError(
            f"画像output(rendered/)の生成数がページ数と一致しません: "
            f"期待{expected_page_count}枚に対し{len(image_paths)}枚しか確認できませんでした。"
        )
    invalid = [str(p) for p in image_paths if not Path(p).exists() or Path(p).stat().st_size == 0]
    if invalid:
        raise ValueError(f"画像output(rendered/)に生成されていない、または空のファイルがあります: {', '.join(invalid)}")


def _verify_expected_outputs(
    output_dir: Path, resolved_format: str, expected_page_count: int = 0, image_paths: list[Path] | None = None
) -> None:
    """`_generate_formatted_outputs()`実行後、指定したoutput-formatの成果物が実際に
    生成されている（かつ空でない）かを検証する。生成されていない場合は「exit 0だが成果物が無い」
    という実質失敗を防ぐため、ValueError（呼び出し元でexit 1になる）を送出する。
    """
    _verify_expected_images(resolved_format, expected_page_count, image_paths or [])

    missing = [
        str(path)
        for path in _expected_output_paths(output_dir, resolved_format)
        if not path.exists() or path.stat().st_size == 0
    ]
    if missing:
        raise ValueError(
            f"指定されたoutput-format({resolved_format})の成果物が生成されませんでした: {', '.join(missing)}"
        )


def _generate_formatted_outputs(
    document: LessonDocument,
    output_dir: Path,
    resolved_format: str,
    font_path: str | None = None,
    logger: ExecutionLogger | None = None,
) -> None:
    """editable/lesson_pages.json相当の正データから、指定形式の完成outputを生成する。

    rendered/(画像)・canva/(Canva指示書)・exports/(PDF/PPTX/DOCX/Markdown)に出力する。
    「json」はeditable中間ファイル自体が対象のため、ここでは追加ファイルを生成しない。
    font_pathは画像output(rendered/・PPTX内の画像)の日本語テキスト合成に使うフォントを明示指定する
    （省略時は環境の日本語フォントを自動探索し、見つからなければ警告のうえPillow既定フォントを使う）。
    生成後、指定した形式の成果物が実際に作られたかを検証する（実質失敗を正常終了扱いにしないため）。
    """
    needs_images = resolved_format in ("image", "pptx", "all")
    image_paths: list[Path] = []
    if needs_images:
        image_paths = render_document_images(document, output_dir, output_dir / "rendered", font_path=font_path)

    if resolved_format in ("pdf", "all"):
        write_pdf(output_dir / "exports" / f"{_EXPORT_BASENAME}.pdf", document)
    if resolved_format in ("pptx", "all"):
        write_pptx_export(output_dir / "exports" / f"{_EXPORT_BASENAME}.pptx", document, image_paths)
    if resolved_format in ("docx", "all"):
        write_docx(output_dir / "exports" / f"{_EXPORT_BASENAME}.docx", document)
    if resolved_format in ("md", "all"):
        write_text(output_dir / "exports" / f"{_EXPORT_BASENAME}.md", render_brushup(document))
    if resolved_format in ("canva", "all"):
        write_text(output_dir / "canva" / "canva_design.md", render_canva_design(document))

    _verify_expected_outputs(
        output_dir, resolved_format, expected_page_count=len(document.pages), image_paths=image_paths
    )

    if logger:
        if needs_images and resolved_format != "pptx":
            _PREVIEW_COUNT = 5
            for path in image_paths[:_PREVIEW_COUNT]:
                logger.record_generated_file(path)
            if len(image_paths) > _PREVIEW_COUNT:
                logger.record_generated_file(f"... ({len(image_paths)} files total)")
            logger.add_section("RENDERED_IMAGES", {"rendered_files_count": len(image_paths)})
        for path in _expected_output_paths(output_dir, resolved_format):
            logger.record_generated_file(path)


def _validate_ocr_precondition(
    imported: dict[str, object], mode: str, allow_empty_ocr: bool, logger: ExecutionLogger | None = None
) -> None:
    """画像input + OCR必須モード(proofread/restructure)で、OCRが実質使えない・全ページ空の
    まま「空データで成功」させないための事前チェック。`--allow-empty-ocr`で明示的に許可された
    場合はスキップする（後方互換・テスト用途）。

    PDF/PPTX入力はOCRではなくネイティブなテキスト抽出を使うため対象外（呼び出し側でinput_kindが
    "image"の場合のみ呼び出す）。
    """
    if mode not in OCR_REQUIRED_MODES:
        return

    pages = imported.get("pages", [])
    if not pages:
        return

    ocr_status = get_ocr_environment_status()
    if logger:
        logger.add_section("OCR", {
            "tesseract_available": ocr_status["tesseract_available"],
            "tesseract_path": ocr_status["tesseract_path"],
            "tesseract_on_path": ocr_status["tesseract_on_path"],
            "japanese_available": ocr_status["japanese_available"],
            "brew_path": ocr_status["brew_path"],
            "warnings": ocr_status["warnings"],
        })

    if allow_empty_ocr:
        degraded = not ocr_status["tesseract_available"] or not ocr_status["japanese_available"] or all(
            not page.get("lines") for page in pages
        )
        if degraded:
            message = (
                "WARNING: OCR environment is degraded, but continuing because --allow-empty-ocr was specified.\n"
                "警告: OCR環境が整っていませんが、--allow-empty-ocrが指定されているため処理を継続します。"
            )
            print(message, file=sys.stderr)
            if logger:
                logger.warn(message)
        elif logger:
            logger.warn("--allow-empty-ocrが指定されています（OCR環境は利用可能でした）。")
        return

    if not ocr_status["tesseract_available"]:
        message = format_ocr_required_tesseract_missing_error(mode, ocr_status)
        print(message, file=sys.stderr)
        if logger:
            logger.error(message)
        raise SystemExit(1)
    if not ocr_status["japanese_available"]:
        message = format_ocr_required_japanese_missing_error(mode)
        print(message, file=sys.stderr)
        if logger:
            logger.error(message)
        raise SystemExit(1)

    empty_pages = [page for page in pages if not page.get("lines")]
    if len(empty_pages) == len(pages):
        message = format_ocr_required_all_pages_empty_error(mode)
        print(message, file=sys.stderr)
        if logger:
            logger.error(message)
        raise SystemExit(1)
    if empty_pages:
        message = format_partial_pages_empty_warning(len(empty_pages), len(pages))
        print(message, file=sys.stderr)
        if logger:
            logger.warn(message)


def build_all(
    input_path: str,
    mode: str,
    output_dir: str | Path,
    requirements_path: str | None = None,
    output_format: str = "same",
    compat_output: bool = True,
    font_path: str | None = None,
    allow_empty_ocr: bool = False,
    logger: ExecutionLogger | None = None,
) -> None:
    """元資料(画像/PDF/PPTX)から成果物一式を一括生成する（build-allコマンドの本体）。

    imported_pages.json/lesson_pages.jsonはシステムが生成する中間ファイルであり、
    作成者が手作業で用意するものではない。**正式な編集対象は`output/editable/lesson_pages.json`
    のみ、正式なCanva指示書は`output/canva/canva_design.md`のみ、正式な完成output（Markdown/
    DOCX/PDF/PPTX）は`output/exports/`のみ**であり、`output_dir`直下には通常ユーザーが使う
    完成outputを置かない。

    Phase 8時点は`output_dir`直下に`lesson_pages.json`/`canva_design.md`/`brushup.md`/
    `brushup.docx`/`brushup.pdf`を生成していたが、Phase 9で追加した`editable/`/`canva/`/
    `exports/`と役割が重複し紛らわしいため、`output/compat/`配下にまとめた
    （`compat_output=False`で無効化できる。既定は有効＝Phase 8からの利用手順を大きく変えない）。
    `scenario/`/`review_report.md`は正式outputとの役割重複が無いため、従来通り`output_dir`
    直下に生成する。

    font_pathは画像output(rendered/・PPTX内の画像)の日本語テキスト合成に使うフォントを明示指定する。

    画像input + `proofread`/`restructure`（OCR必須モード）でOCRが実質使えない場合
    （Tesseract未導入・日本語言語データ無し・全ページOCR結果が空）は、警告のうえ空データのまま
    成功させるのではなく、明確なエラーを出して非ゼロ終了する（Phase 10.1追加修正）。
    `allow_empty_ocr=True`（`--allow-empty-ocr`）でこのチェックをスキップできる。

    取り込みページが0件、または指定したoutput-formatの成果物が生成されない場合も、実質失敗を
    正常終了扱いにしないためエラーにする（Phase 10.2）。
    """
    output_dir = Path(output_dir)
    assets_dir = output_dir / "assets"
    imported_pages_path = output_dir / "imported_pages.json"
    input_kind = _detect_input_kind(input_path)

    if logger:
        logger.add_section("INPUT", {
            "input_path": str(input_path),
            "input_kind": input_kind,
            "mode": mode,
            "output_format": output_format,
            "output_dir": str(output_dir),
        })

    # 画像inputの場合、OCR関連の警告は_validate_ocr_precondition()側で集約して表示するため、
    # import_source()側の重複表示をquiet=Trueで抑制する（Phase 10.2追加修正）。
    imported = run_import_source(input_path, imported_pages_path, assets_dir, quiet=(input_kind == "image"))
    pages = imported.get("pages", [])

    if logger:
        logger.record_generated_file(imported_pages_path)
        logger.add_section("INPUT_RESULT", {
            "imported_pages": len(pages),
            "ocr_success_pages": sum(1 for p in pages if p.get("lines")),
            "ocr_empty_pages": sum(1 for p in pages if not p.get("lines")),
        })

    if not pages:
        message = f"取り込み対象のページがありません（入力: {input_path}）。処理を継続できません。"
        if logger:
            logger.error(message)
        raise ValueError(message)

    if input_kind == "image":
        _validate_ocr_precondition(imported, mode, allow_empty_ocr, logger=logger)

    document, _plan = build_lesson_pages(mode, str(imported_pages_path), requirements_path)
    write_lesson_pages_json(output_dir / "editable" / "lesson_pages.json", document)
    if logger:
        logger.record_generated_file(output_dir / "editable" / "lesson_pages.json")

    if compat_output:
        write_lesson_pages_json(output_dir / "compat" / "lesson_pages.json", document)
        write_text(output_dir / "compat" / "canva_design.md", render_canva_design(document))
        write_text(output_dir / "compat" / "brushup.md", render_brushup(document))
        write_docx(output_dir / "compat" / "brushup.docx", document)
        write_pdf(output_dir / "compat" / "brushup.pdf", document)

    write_scenario_outputs(output_dir / "scenario", document)
    write_text(output_dir / "review_report.md", render_review_report(document))
    if logger:
        logger.record_generated_file(output_dir / "review_report.md")

    resolved_format = resolve_output_format(output_format, input_kind)
    _generate_formatted_outputs(document, output_dir, resolved_format, font_path=font_path, logger=logger)


def regenerate(
    input_path: str,
    output_format: str,
    output_dir: str | Path | None = None,
    font_path: str | None = None,
    logger: ExecutionLogger | None = None,
) -> None:
    """editable中間ファイル（例: output/editable/lesson_pages.json）から成果物を再生成する。

    ユーザーがeditable中間ファイルを編集した後、完成画像・PDF・PPTX・DOCX・Canva指示書等を
    作り直すための導線。完成画像やPDFを直接編集するのではなく、この中間ファイルを編集して
    再生成することを想定する。font_pathは画像output(rendered/・PPTX内の画像)の日本語テキスト
    合成に使うフォントを明示指定する。

    入力ファイルが存在しない・JSON構文が不正な場合は`load_lesson_document()`が
    `FileNotFoundError`/`ValueError`を送出し、呼び出し元で非ゼロ終了になる。pagesが0件、または
    指定したoutput-formatの成果物が生成されない場合も同様にエラーにする（Phase 10.2）。
    """
    editable_path = Path(input_path)

    if logger:
        logger.add_section("INPUT", {
            "input_path": str(editable_path),
            "output_format": output_format,
        })

    document = load_lesson_document(editable_path)

    if logger:
        logger.add_section("INPUT_RESULT", {"pages": len(document.pages)})

    if not document.pages:
        message = f"editable中間ファイルにページがありません（入力: {editable_path}）。処理を継続できません。"
        if logger:
            logger.error(message)
        raise ValueError(message)

    resolved_output_dir = Path(output_dir) if output_dir else editable_path.resolve().parent.parent
    resolved_format = "all" if output_format == "same" else output_format
    _generate_formatted_outputs(document, resolved_output_dir, resolved_format, font_path=font_path, logger=logger)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI教材ブラッシュアップシステム")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "check-ocr", help="OCR環境(tesseract/日本語言語データ/Homebrew)を診断する"
    )

    import_source_parser = subparsers.add_parser(
        "import-source", help="元資料(画像/PDF/PPTX)からimported_pages.json(pages形式)を生成"
    )
    import_source_parser.add_argument(
        "--input", required=True, help="元資料のパス（画像ディレクトリ、画像ファイル、PDF、PPTXのいずれか）"
    )
    import_source_parser.add_argument("--output", required=True, help="出力imported_pages.json")
    import_source_parser.add_argument(
        "--assets-dir", default=None, help="画像アセットの保存先（省略時は出力先と同階層のassets/）"
    )

    build_all_parser = subparsers.add_parser(
        "build-all", help="元資料(画像/PDF/PPTX)から成果物一式(lesson_pages.json〜scenario等)を一括生成"
    )
    build_all_parser.add_argument(
        "--input", required=True, help="元資料のパス（画像ディレクトリ、画像ファイル、PDF、PPTXのいずれか）"
    )
    build_all_parser.add_argument(
        "--mode",
        choices=["proofread", "restructure"],
        default="proofread",
        help="生成モード（proofread: 校正・整形 / restructure: 再構成。デフォルトはproofread）",
    )
    build_all_parser.add_argument("--requirements", default=None, help="要件定義JSON（restructureモードで任意）")
    build_all_parser.add_argument("--output-dir", required=True, help="出力先ディレクトリ")
    build_all_parser.add_argument(
        "--output-format",
        choices=OUTPUT_FORMAT_CHOICES,
        default="same",
        help="完成outputの形式（same: 入力の性質に合わせる[既定] / image / pdf / pptx / docx / md / canva / json / all）",
    )
    build_all_parser.add_argument(
        "--no-compat-output",
        dest="compat_output",
        action="store_false",
        default=True,
        help="Phase 8互換output(output/compat/lesson_pages.json・canva_design.md・brushup.md・brushup.docx・brushup.pdf)を生成しない（既定は生成する）",
    )
    build_all_parser.add_argument(
        "--font-path",
        default=None,
        help="画像output(rendered//PPTX内画像)の日本語テキスト合成に使うフォントファイルのパス（省略時は環境の日本語フォントを自動探索）",
    )
    build_all_parser.add_argument(
        "--allow-empty-ocr",
        action="store_true",
        default=False,
        help=(
            "画像input+proofread/restructureでOCRが実質使えない場合（Tesseract未導入・"
            "日本語言語データ無し・全ページOCR結果が空）でも、エラー終了せず空データのまま処理を"
            "続行する（既定は無効＝エラー終了する。テスト・開発用途向け）"
        ),
    )

    regenerate_parser = subparsers.add_parser(
        "regenerate",
        help="editable中間ファイル(output/editable/lesson_pages.json等)を編集した後、成果物を再生成する",
    )
    regenerate_parser.add_argument(
        "--input", required=True, help="編集済みのlesson_pages形式JSON（例: output/editable/lesson_pages.json）"
    )
    regenerate_parser.add_argument(
        "--output-format",
        choices=OUTPUT_FORMAT_CHOICES,
        default="all",
        help="再生成する完成outputの形式（既定はall。sameが指定された場合もallとして扱う）",
    )
    regenerate_parser.add_argument(
        "--output-dir",
        default=None,
        help="出力先ディレクトリ（省略時は--inputの2階層上。例: output/editable/lesson_pages.json → output/）",
    )
    regenerate_parser.add_argument(
        "--font-path",
        default=None,
        help="画像output(rendered//PPTX内画像)の日本語テキスト合成に使うフォントファイルのパス（省略時は環境の日本語フォントを自動探索）",
    )

    lesson_pages_parser = subparsers.add_parser(
        "lesson-pages", help="正データとなるlesson_pages.jsonを生成"
    )
    lesson_pages_parser.add_argument(
        "--mode",
        choices=["proofread", "restructure", "generate"],
        default="proofread",
        help="生成モード（proofread: 校正・整形 / restructure: 再構成 / generate: 新規生成。デフォルトはproofread）",
    )
    lesson_pages_parser.add_argument(
        "--input", help="入力JSON（pages形式またはlesson_pages形式）。proofread/restructureモードで必須"
    )
    lesson_pages_parser.add_argument(
        "--requirements", help="要件定義JSON。generateモードで必須、restructureモードで任意"
    )
    lesson_pages_parser.add_argument("--output", required=True, help="出力lesson_pages.json")
    lesson_pages_parser.add_argument(
        "--plan-output",
        help="restructureモードの再構成プランを出力するJSONパス（restructure以外では無視される。任意）",
    )

    review_report_parser = subparsers.add_parser(
        "review-report", help="各ページのrole/source_page_no対応を制作者確認用にMarkdownで出力"
    )
    review_report_parser.add_argument("--input", required=True, help="入力lesson_pages.json")
    review_report_parser.add_argument("--output", required=True, help="出力Markdown")

    generate_parser = subparsers.add_parser("generate", help="教材ブラッシュアップ設計書を生成")
    generate_parser.add_argument("--input", required=True, help="入力JSON")
    generate_parser.add_argument("--output", required=True, help="出力Markdown")

    canva_parser = subparsers.add_parser("canva", help="Canva向け設計書を生成")
    canva_parser.add_argument("--input", required=True, help="入力JSON")
    canva_parser.add_argument("--output", required=True, help="出力Markdown")

    llm_handoff_parser = subparsers.add_parser(
        "llm-handoff",
        help="editable/lesson_pages.jsonから、ChatGPT/Claude等へ手作業で貼り付けるためのMarkdownを生成"
        "（LLM出力の自動取り込みは行わない）",
    )
    llm_handoff_parser.add_argument("--input", required=True, help="入力lesson_pages.json（editable配下等）")
    llm_handoff_parser.add_argument(
        "--output", default="output/llm_handoff.md", help="出力Markdown（既定: output/llm_handoff.md）"
    )
    llm_handoff_parser.add_argument(
        "--page-start", type=int, default=None, help="対象とする先頭page_no（省略時は先頭ページから）"
    )
    llm_handoff_parser.add_argument(
        "--page-end", type=int, default=None, help="対象とする末尾page_no（省略時は末尾ページまで）"
    )

    edit_plan_template_parser = subparsers.add_parser(
        "edit-plan-template",
        help="editable/lesson_pages.jsonから、LLM改善案の採用判断シート（edit_plan_template.md）を生成"
        "（LLM出力の自動取り込み・自動マージは行わない）",
    )
    edit_plan_template_parser.add_argument(
        "--input", required=True, help="入力lesson_pages.json（editable配下等）"
    )
    edit_plan_template_parser.add_argument(
        "--output",
        default="output/edit_plan_template.md",
        help="出力Markdown（既定: output/edit_plan_template.md）",
    )

    ocr_check_parser = subparsers.add_parser(
        "ocr-check",
        help="lesson_pages.jsonのOCR品質（誤認識・文字化け・不自然な表記）を検出し、"
        "レポートと補正候補JSONを生成（自動修正・自動反映は行わない）",
    )
    ocr_check_parser.add_argument("--input", required=True, help="入力lesson_pages.json（editable配下等）")
    ocr_check_parser.add_argument(
        "--output", default="output/ocr_check_report.md", help="出力Markdownレポート（既定: output/ocr_check_report.md）"
    )
    ocr_check_parser.add_argument(
        "--candidates-output",
        default="output/ocr_correction_candidates.json",
        help="補正候補JSONの出力先（既定: output/ocr_correction_candidates.json）",
    )
    ocr_check_parser.add_argument(
        "--ocr-patterns",
        default=None,
        help="OCRパターン外部辞書のパス（既定: config/ocr_patterns.json。無ければ組み込みデフォルトのみ使用）",
    )

    apply_ocr_corrections_parser = subparsers.add_parser(
        "apply-ocr-corrections",
        help="ocr-checkが生成したocr_correction_candidates.jsonのうち、status: approvedの候補だけを"
        "lesson_pages.jsonへ反映（元ファイルは上書きしない。自動承認は行わない）",
    )
    apply_ocr_corrections_parser.add_argument(
        "--input", required=True, help="入力lesson_pages.json（editable配下等。上書きしない）"
    )
    apply_ocr_corrections_parser.add_argument(
        "--candidates", required=True, help="ocr-checkが生成したocr_correction_candidates.json"
    )
    apply_ocr_corrections_parser.add_argument(
        "--output",
        default="output/editable/lesson_pages.ocr_fixed.json",
        help="補正済みlesson_pages.jsonの出力先（既定: output/editable/lesson_pages.ocr_fixed.json）",
    )
    apply_ocr_corrections_parser.add_argument(
        "--report", default="output/ocr_apply_report.md", help="反映結果レポートの出力先（既定: output/ocr_apply_report.md）"
    )
    apply_ocr_corrections_parser.add_argument(
        "--dry-run", action="store_true", help="出力JSONを生成せず、反映予定の内容だけレポートに出す"
    )

    apply_llm_suggestions_parser = subparsers.add_parser(
        "apply-llm-suggestions",
        help="ChatGPT/Claude等の回答Markdownを読み込み、ページ別の改善候補として構造化"
        "（lesson_pages.jsonへの自動反映は行わない）",
    )
    apply_llm_suggestions_parser.add_argument(
        "--lesson-pages", required=True, help="元になるlesson_pages.json（editable配下・OCR補正済み等）"
    )
    apply_llm_suggestions_parser.add_argument(
        "--suggestions", required=True, help="ChatGPT/Claude等の回答Markdown"
    )
    apply_llm_suggestions_parser.add_argument(
        "--candidates-output",
        default="output/llm_suggestion_candidates.json",
        help="構造化した改善候補JSONの出力先（既定: output/llm_suggestion_candidates.json）",
    )
    apply_llm_suggestions_parser.add_argument(
        "--report",
        default="output/llm_suggestion_report.md",
        help="人間確認用Markdownレポートの出力先（既定: output/llm_suggestion_report.md）",
    )

    docx_parser = subparsers.add_parser("docx", help="Word教材(docx)を生成")
    docx_parser.add_argument("--input", required=True, help="入力JSON")
    docx_parser.add_argument("--output", required=True, help="出力docx")

    pdf_parser = subparsers.add_parser("pdf", help="PDF教材を生成")
    pdf_parser.add_argument("--input", required=True, help="入力JSON")
    pdf_parser.add_argument("--output", required=True, help="出力pdf")

    scenario_parser = subparsers.add_parser(
        "scenario", help="動画生成用シナリオ一式(JSON/Markdown/VOICEVOX/シーン分割JSON)を生成"
    )
    scenario_parser.add_argument("--input", required=True, help="入力JSON")
    scenario_parser.add_argument("--output-dir", required=True, help="出力先ディレクトリ")

    canva_sync_parser = subparsers.add_parser(
        "canva-sync", help="Canva APIでページごとのデザインを作成（CANVA_API_KEY未設定時はモック動作）"
    )
    canva_sync_parser.add_argument("--input", required=True, help="入力JSON")
    canva_sync_parser.add_argument("--output", required=True, help="出力レポートJSON")

    wp_publish_parser = subparsers.add_parser(
        "wp-publish",
        help="WordPressへ記事を作成（画像アップロード→記事作成→カテゴリ→タグ→アイキャッチ設定）。"
        "認証情報未設定時はモック動作",
    )
    wp_publish_parser.add_argument("--input", required=True, help="入力JSON")
    wp_publish_parser.add_argument("--output", required=True, help="出力レポートJSON")
    wp_publish_parser.add_argument("--image-dir", default="input/raw_images", help="画像ファイルの探索元ディレクトリ")
    wp_publish_parser.add_argument("--categories", default="", help="カンマ区切りのカテゴリ名")
    wp_publish_parser.add_argument("--tags", default="", help="カンマ区切りのタグ名")
    wp_publish_parser.add_argument(
        "--status", default="draft", help="投稿ステータス(draft/publish/future/pending/privateのいずれか)"
    )

    args = parser.parse_args()

    # lesson-pagesはproofread/restructure/generateの3モードを1つのサブコマンドで扱うため、
    # ログファイル名はコマンド名ではなくモード名を使う（logs/..._generate.log等。
    # 詳細はCLAUDE_RULES.md「ログ出力の共通設計ルール」参照）。
    log_command = args.mode if args.command == "lesson-pages" else args.command
    logger = ExecutionLogger(log_command, sys.argv[1:])
    original_stderr = sys.stderr
    tee_stderr = TeeStderr(original_stderr)
    sys.stderr = tee_stderr

    exit_code = 0
    error: BaseException | None = None
    try:
        if args.command == "check-ocr":
            ocr_status = get_ocr_environment_status()
            logger.add_section("OCR", {
                "tesseract_available": ocr_status["tesseract_available"],
                "tesseract_path": ocr_status["tesseract_path"],
                "japanese_available": ocr_status["japanese_available"],
                "brew_available": ocr_status["brew_available"],
                "brew_path": ocr_status["brew_path"],
                "ocr_ready": ocr_status["ocr_ready"],
            })
            print(format_environment_report(ocr_status))
        elif args.command == "import-source":
            imported = run_import_source(args.input, args.output, args.assets_dir)
            logger.add_section("INPUT", {"input_path": args.input})
            logger.add_section("INPUT_RESULT", {"pages": len(imported.get("pages", []))})
            validate_generated_json_pages(args.output, len(imported.get("pages", [])), "import-source")
            logger.record_generated_file(args.output)
        elif args.command == "build-all":
            build_all(
                args.input, args.mode, args.output_dir, args.requirements,
                args.output_format, args.compat_output, args.font_path,
                args.allow_empty_ocr, logger=logger,
            )
        elif args.command == "regenerate":
            regenerate(args.input, args.output_format, args.output_dir, args.font_path, logger=logger)
        elif args.command == "lesson-pages":
            document, plan = build_lesson_pages(args.mode, args.input, args.requirements)
            write_lesson_pages_json(args.output, document)
            logger.add_section("INPUT", {"input_path": args.input, "mode": args.mode})
            logger.add_section("INPUT_RESULT", {"pages": len(document.pages)})
            validate_generated_json_pages(args.output, len(document.pages), "lesson-pages")
            logger.record_generated_file(args.output)
            if args.plan_output and plan is not None:
                write_text(args.plan_output, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
                logger.record_generated_file(args.plan_output)
        elif args.command == "review-report":
            document = load_lesson_document(args.input)
            write_text(args.output, render_review_report(document))
            validate_generated_file(args.output, "review-report")
            logger.record_generated_file(args.output)
        elif args.command == "generate":
            document = load_lesson_document(args.input)
            write_text(args.output, render_brushup(document))
            validate_generated_file(args.output, "generate")
            logger.record_generated_file(args.output)
        elif args.command == "canva":
            document = load_lesson_document(args.input)
            write_text(args.output, render_canva_design(document))
            validate_generated_file(args.output, "canva")
            logger.record_generated_file(args.output)
        elif args.command == "llm-handoff":
            document = load_lesson_document(args.input)
            write_text(
                args.output,
                render_llm_handoff_markdown(document, page_start=args.page_start, page_end=args.page_end),
            )
            validate_generated_file(args.output, "llm-handoff")
            logger.add_section("INPUT", {
                "input_path": args.input,
                "page_start": args.page_start,
                "page_end": args.page_end,
            })
            logger.record_generated_file(args.output)
        elif args.command == "edit-plan-template":
            document = load_lesson_document(args.input)
            write_text(args.output, render_edit_plan_template_markdown(document))
            validate_generated_file(args.output, "edit-plan-template")
            logger.add_section("INPUT", {"input_path": args.input})
            logger.record_generated_file(args.output)
        elif args.command == "ocr-check":
            document = load_lesson_document(args.input)
            patterns, patterns_meta = load_ocr_patterns(args.ocr_patterns)
            candidates_data = build_ocr_correction_candidates(
                document, source_file=args.input, patterns=patterns, patterns_meta=patterns_meta
            )
            write_correction_candidates_json(candidates_data, args.candidates_output)
            validate_generated_file(args.candidates_output, "ocr-check(candidates)")
            write_text(
                args.output,
                render_ocr_check_report_markdown(document, candidates_data, candidates_output=args.candidates_output),
            )
            validate_generated_file(args.output, "ocr-check")
            logger.add_section("INPUT", {"input_path": args.input, "ocr_patterns": patterns_meta})
            logger.add_section("OCR_CHECK", candidates_data["summary"])
            logger.record_generated_file(args.candidates_output)
            logger.record_generated_file(args.output)
        elif args.command == "apply-ocr-corrections":
            document = load_lesson_document(args.input)
            candidates_data = load_correction_candidates(args.candidates)
            result = apply_ocr_corrections(document, candidates_data)
            if not args.dry_run:
                write_lesson_pages(args.output, result["document"])
                validate_generated_file(args.output, "apply-ocr-corrections")
            write_text(
                args.report,
                render_ocr_apply_report_markdown(
                    result,
                    candidates_data,
                    input_path=args.input,
                    candidates_path=args.candidates,
                    output_path=args.output,
                    report_path=args.report,
                    dry_run=args.dry_run,
                ),
            )
            validate_generated_file(args.report, "apply-ocr-corrections(report)")
            logger.add_section("INPUT", {"input_path": args.input, "candidates_path": args.candidates, "dry_run": args.dry_run})
            logger.add_section("OCR_APPLY", {
                "applied_count": len(result["applied"]),
                "skipped_count": len(result["skipped"]),
            })
            if not args.dry_run:
                logger.record_generated_file(args.output)
            logger.record_generated_file(args.report)
        elif args.command == "apply-llm-suggestions":
            document = load_lesson_document(args.lesson_pages)
            suggestions_text = load_llm_suggestions_markdown(args.suggestions)
            parsed = parse_llm_suggestions(suggestions_text)
            candidates_data = build_llm_suggestion_candidates(
                document, parsed, source_lesson_pages=args.lesson_pages, source_suggestions=args.suggestions
            )
            write_llm_suggestion_candidates_json(args.candidates_output, candidates_data)
            validate_generated_file(args.candidates_output, "apply-llm-suggestions(candidates)")
            write_text(
                args.report,
                render_llm_suggestion_report_markdown(
                    document, candidates_data,
                    lesson_pages_path=args.lesson_pages, suggestions_path=args.suggestions,
                    candidates_output=args.candidates_output, report_path=args.report,
                ),
            )
            validate_generated_file(args.report, "apply-llm-suggestions")
            logger.add_section("INPUT", {"lesson_pages_path": args.lesson_pages, "suggestions_path": args.suggestions})
            logger.add_section("LLM_SUGGESTIONS", candidates_data["summary"])
            logger.record_generated_file(args.candidates_output)
            logger.record_generated_file(args.report)
        elif args.command == "docx":
            document = load_lesson_document(args.input)
            write_docx(args.output, document)
            validate_generated_file(args.output, "docx")
            logger.record_generated_file(args.output)
        elif args.command == "pdf":
            document = load_lesson_document(args.input)
            write_pdf(args.output, document)
            validate_generated_file(args.output, "pdf")
            logger.record_generated_file(args.output)
        elif args.command == "scenario":
            document = load_lesson_document(args.input)
            write_scenario_outputs(args.output_dir, document)
            scenario_dir = Path(args.output_dir)
            for scenario_file in ("scenario.json", "scenario.md", "voicevox.txt", "scene.json"):
                validate_generated_file(scenario_dir / scenario_file, "scenario")
            logger.record_generated_file(args.output_dir)
        elif args.command == "canva-sync":
            project = load_project(args.input)
            write_canva_sync_report(args.output, project)
            validate_generated_file(args.output, "canva-sync")
            logger.record_generated_file(args.output)
        elif args.command == "wp-publish":
            project = load_project(args.input)
            categories = [c.strip() for c in args.categories.split(",") if c.strip()]
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            write_wordpress_publish_report(
                args.output,
                project,
                image_dir=args.image_dir,
                category_names=categories,
                tag_names=tags,
                status=args.status,
            )
            validate_generated_file(args.output, "wp-publish")
            logger.record_generated_file(args.output)
    except (FileNotFoundError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        logger.error(str(e))
        exit_code = 1
        error = e
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
        error = e
    finally:
        sys.stderr = original_stderr
        logger.finalize(exit_code, captured_stderr=tee_stderr.captured)

    if exit_code:
        if isinstance(error, SystemExit):
            raise error
        raise SystemExit(exit_code) from error


if __name__ == "__main__":
    main()
