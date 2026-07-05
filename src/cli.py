from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .canva_client import write_canva_sync_report
from .canva_renderer import render_canva_design
from .docx_renderer import write_docx
from .image_renderer import render_document_images
from .import_source import import_source
from .lesson_pages import LessonDocument, build_lesson_pages, render_review_report, write_lesson_pages_json
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


def run_import_source(input_path: str, output_path: str | Path, assets_dir: str | Path | None = None) -> None:
    """元資料(画像/PDF/PPTX)からimported_pages.json互換のJSONを生成して書き出す。"""
    output_path = Path(output_path)
    resolved_assets_dir = Path(assets_dir) if assets_dir else output_path.parent / "assets"
    imported = import_source(input_path, resolved_assets_dir)
    write_text(output_path, json.dumps(imported, ensure_ascii=False, indent=2) + "\n")


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


def _generate_formatted_outputs(document: LessonDocument, output_dir: Path, resolved_format: str) -> None:
    """editable/lesson_pages.json相当の正データから、指定形式の完成outputを生成する。

    rendered/(画像)・canva/(Canva指示書)・exports/(PDF/PPTX/DOCX/Markdown)に出力する。
    「json」はeditable中間ファイル自体が対象のため、ここでは追加ファイルを生成しない。
    """
    needs_images = resolved_format in ("image", "pptx", "all")
    image_paths: list[Path] = []
    if needs_images:
        image_paths = render_document_images(document, output_dir, output_dir / "rendered")

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


def build_all(
    input_path: str,
    mode: str,
    output_dir: str | Path,
    requirements_path: str | None = None,
    output_format: str = "same",
    compat_output: bool = True,
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
    """
    output_dir = Path(output_dir)
    assets_dir = output_dir / "assets"
    imported_pages_path = output_dir / "imported_pages.json"

    run_import_source(input_path, imported_pages_path, assets_dir)

    document, _plan = build_lesson_pages(mode, str(imported_pages_path), requirements_path)
    write_lesson_pages_json(output_dir / "editable" / "lesson_pages.json", document)

    if compat_output:
        write_lesson_pages_json(output_dir / "compat" / "lesson_pages.json", document)
        write_text(output_dir / "compat" / "canva_design.md", render_canva_design(document))
        write_text(output_dir / "compat" / "brushup.md", render_brushup(document))
        write_docx(output_dir / "compat" / "brushup.docx", document)
        write_pdf(output_dir / "compat" / "brushup.pdf", document)

    write_scenario_outputs(output_dir / "scenario", document)
    write_text(output_dir / "review_report.md", render_review_report(document))

    resolved_format = resolve_output_format(output_format, _detect_input_kind(input_path))
    _generate_formatted_outputs(document, output_dir, resolved_format)


def regenerate(input_path: str, output_format: str, output_dir: str | Path | None = None) -> None:
    """editable中間ファイル（例: output/editable/lesson_pages.json）から成果物を再生成する。

    ユーザーがeditable中間ファイルを編集した後、完成画像・PDF・PPTX・DOCX・Canva指示書等を
    作り直すための導線。完成画像やPDFを直接編集するのではなく、この中間ファイルを編集して
    再生成することを想定する。
    """
    editable_path = Path(input_path)
    document = load_lesson_document(editable_path)
    resolved_output_dir = Path(output_dir) if output_dir else editable_path.resolve().parent.parent
    resolved_format = "all" if output_format == "same" else output_format
    _generate_formatted_outputs(document, resolved_output_dir, resolved_format)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI教材ブラッシュアップシステム")
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    try:
        if args.command == "import-source":
            run_import_source(args.input, args.output, args.assets_dir)
        elif args.command == "build-all":
            build_all(args.input, args.mode, args.output_dir, args.requirements, args.output_format, args.compat_output)
        elif args.command == "regenerate":
            regenerate(args.input, args.output_format, args.output_dir)
        elif args.command == "lesson-pages":
            document, plan = build_lesson_pages(args.mode, args.input, args.requirements)
            write_lesson_pages_json(args.output, document)
            if args.plan_output and plan is not None:
                write_text(args.plan_output, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        elif args.command == "review-report":
            document = load_lesson_document(args.input)
            write_text(args.output, render_review_report(document))
        elif args.command == "generate":
            document = load_lesson_document(args.input)
            write_text(args.output, render_brushup(document))
        elif args.command == "canva":
            document = load_lesson_document(args.input)
            write_text(args.output, render_canva_design(document))
        elif args.command == "docx":
            document = load_lesson_document(args.input)
            write_docx(args.output, document)
        elif args.command == "pdf":
            document = load_lesson_document(args.input)
            write_pdf(args.output, document)
        elif args.command == "scenario":
            document = load_lesson_document(args.input)
            write_scenario_outputs(args.output_dir, document)
        elif args.command == "canva-sync":
            project = load_project(args.input)
            write_canva_sync_report(args.output, project)
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
    except (FileNotFoundError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
