from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .canva_client import write_canva_sync_report
from .canva_renderer import render_canva_design
from .docx_renderer import write_docx
from .import_source import import_source
from .lesson_pages import build_lesson_pages, render_review_report, write_lesson_pages_json
from .parser import load_lesson_document, load_project
from .pdf_renderer import write_pdf
from .renderer import render_brushup
from .scenario_renderer import write_scenario_outputs
from .wordpress_client import write_wordpress_publish_report


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


def build_all(
    input_path: str,
    mode: str,
    output_dir: str | Path,
    requirements_path: str | None = None,
) -> None:
    """元資料(画像/PDF/PPTX)から成果物一式を一括生成する（build-allコマンドの本体）。

    imported_pages.json/lesson_pages.jsonはシステムが生成する中間ファイルであり、
    作成者が手作業で用意するものではない。
    """
    output_dir = Path(output_dir)
    assets_dir = output_dir / "assets"
    imported_pages_path = output_dir / "imported_pages.json"
    lesson_pages_path = output_dir / "lesson_pages.json"

    run_import_source(input_path, imported_pages_path, assets_dir)

    document, _plan = build_lesson_pages(mode, str(imported_pages_path), requirements_path)
    write_lesson_pages_json(lesson_pages_path, document)

    write_text(output_dir / "brushup.md", render_brushup(document))
    write_text(output_dir / "canva_design.md", render_canva_design(document))
    write_docx(output_dir / "brushup.docx", document)
    write_pdf(output_dir / "brushup.pdf", document)
    write_scenario_outputs(output_dir / "scenario", document)
    write_text(output_dir / "review_report.md", render_review_report(document))


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
            build_all(args.input, args.mode, args.output_dir, args.requirements)
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
