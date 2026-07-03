import argparse
from pathlib import Path

from .canva_renderer import render_canva_design
from .parser import load_project
from .renderer import render_brushup


def write_text(path: str | Path, text: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI教材ブラッシュアップシステム")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="教材ブラッシュアップ設計書を生成")
    generate_parser.add_argument("--input", required=True, help="入力JSON")
    generate_parser.add_argument("--output", required=True, help="出力Markdown")

    canva_parser = subparsers.add_parser("canva", help="Canva向け設計書を生成")
    canva_parser.add_argument("--input", required=True, help="入力JSON")
    canva_parser.add_argument("--output", required=True, help="出力Markdown")

    args = parser.parse_args()
    project = load_project(args.input)

    if args.command == "generate":
        write_text(args.output, render_brushup(project))
    elif args.command == "canva":
        write_text(args.output, render_canva_design(project))


if __name__ == "__main__":
    main()
