from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 実行時の循環importを避けるため、型チェック専用でのみ`ocr_comparison`を参照する
    # （`ocr_comparison.py`側がこのモジュールを呼び出す構成のため）。
    from .ocr_comparison import ComparisonSummary

# Claude Code向けのOCR画像照合レビュー指示書（CLAUDE_OCR_REVIEW.md）と、Claude Codeが結果を
# 保存する`claude_review/`ディレクトリのREADMEを生成する（Phase 10.10）。
#
# 重要な位置づけ:
# - ここで生成するのは「指示書」と「保存規約の説明」のみ。Claude API・外部送信・自動実行は
#   一切行わない（`build-all`はプロセスを自動起動しない）。
# - 実際の画像照合・候補JSON作成は、この指示書を読んだ別セッションのClaude Codeが行う。
# - `build-all`実行時点では`claude_review/README.md`以外（`pages/`・`progress.json`・
#   `candidates.json`・`review_summary.md`）は生成しない。
# - Apple Visionが利用できず比較を実施できなかった場合は、指示書自体を生成しない
#   （中身の無い比較を照合可能であるかのように見せかけないため）。

CLAUDE_OCR_REVIEW_FILENAME = "CLAUDE_OCR_REVIEW.md"
CLAUDE_REVIEW_DIR_NAME = "claude_review"
CLAUDE_REVIEW_README_FILENAME = "README.md"

_ALLOWED_DECISIONS = ("tesseract", "apple_vision", "merged", "corrected", "unresolved")


def format_page_number_ranges(page_numbers: list[int]) -> str:
    """ページ番号のリストを、連続する区間をまとめた読みやすい表記にする
    （例: [1,2,3,5,7,8,9] -> "1-3, 5, 7-9"）。100ページ以上でも冗長にならないようにするため。
    """
    if not page_numbers:
        return "(なし)"
    ordered = sorted(page_numbers)
    ranges: list[str] = []
    start = prev = ordered[0]
    for n in ordered[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = n
    ranges.append(str(start) if start == prev else f"{start}-{prev}")
    return ", ".join(ranges)


def _relative_output_dir(output_dir: Path) -> str:
    """指示書へ埋め込む`output_dir`表記を、可能な限りプロジェクトルートからの相対パスにする
    （絶対パスを指示書へ埋め込まないため）。呼び出し側は通常`--output-dir`に相対パス
    （例: "output"）を渡す想定だが、絶対パスが渡された場合はカレントディレクトリからの
    相対化を試み、それも出来ない場合はディレクトリ名のみを使う（安全側のフォールバック）。
    """
    try:
        if output_dir.is_absolute():
            rel = output_dir.resolve().relative_to(Path.cwd().resolve())
            return rel.as_posix()
        return output_dir.as_posix()
    except ValueError:
        return output_dir.name


def render_claude_review_readme() -> str:
    """`output/<output-dir>/ocr_comparison/claude_review/README.md`の内容。"""
    return """# claude_review/ ディレクトリについて

このディレクトリは、`CLAUDE_OCR_REVIEW.md`の指示に従ってClaude Codeが元画像とOCR結果を
照合した結果を保存する場所です。

## 保存されるもの（Claude Codeが指示書実行時に作成）

- `pages/page_NNN.json` — ページごとの照合結果（1ページ1ファイル）
- `progress.json` — 全体の進捗（完了ページ・未処理ページ・要確認ページ）
- `candidates.json` — 全ページの結果をまとめた集約JSON
- `review_summary.md` — 人間が確認するための要約Markdown

`build-all`実行時点ではこの`README.md`だけが存在し、他のファイルはまだ生成されていません。

## 中断・再開について

ページ単位で保存されるため、途中で中断しても、次回`CLAUDE_OCR_REVIEW.md`の指示に従って
再実行すれば、既に保存済みの正常なページはスキップされ、未処理のページから再開されます。

## 自動反映されないこと

このディレクトリの内容は、`output/editable/lesson_pages.json`（正式データ）へ自動反映
されません。反映するかどうか・どう反映するかは、人間が`review_summary.md`を確認したうえで
別途判断してください。

## Git管理対象外

このディレクトリは`output/`配下にあるため、プロジェクトの既存方針により
Git管理対象外です（`input/`・`output/`・`logs/evidence/`と同様）。

## 人間確認が必要なページの見方

`review_summary.md`の「人間確認が必要なページ」一覧、または`candidates.json`の
`requires_human_review_pages`を確認してください。該当ページは、元画像から確定できない
箇所が残っているか、Claude Codeが判断に迷ったページです。該当ページの
`pages/page_NNN.json`の`review_notes`・`unresolved_spans`も参考にしてください。
"""


def render_claude_ocr_review_instructions(summary: "ComparisonSummary", output_dir: Path) -> str:
    """Claude Code向けの自己完結したOCR画像照合レビュー指示書を組み立てる。

    実データ（`summary`）から埋め込むのは、ページ総数・ページ番号一覧・相対パス・
    Apple Vision利用可否・要確認ページ・生成日時等の**構造情報のみ**。OCR全文・画像バイナリは
    埋め込まない（Claude Codeが実行時に既存のページ別比較JSON・元画像を直接読む設計のため）。
    """
    rel_dir = _relative_output_dir(output_dir)
    comparison_rel = f"{rel_dir}/ocr_comparison"
    page_numbers = [p.page_no for p in summary.pages]
    page_range_text = format_page_number_ranges(page_numbers)
    first_page = page_numbers[0] if page_numbers else 1
    needs_review_text = (
        format_page_number_ranges(summary.needs_review_pages) if summary.needs_review_pages else "(なし)"
    )

    lines: list[str] = []
    a = lines.append

    a("# Claude Code向け OCR画像照合レビュー指示書")
    a("")
    a(f"（`build-all --ocr-engine tesseract+vision`が自動生成。生成日時: {summary.generated_at}）")
    a("")
    a("このファイルは自己完結した作業指示書です。**このファイルを読むだけで、追加の質問をせず")
    a("最後まで作業を進めてください。** プログラムからの自動呼び出しは行っていません"
      "（Claude API・外部送信・APIキーは一切使用しません）。")
    a("")

    a("## 1. 作業目的")
    a("")
    a("- 元画像を正本（唯一の正解の根拠）として扱う")
    a("- TesseractとApple Visionの結果を元画像と照合する")
    a("- ページ内の部分ごとに、どちらの結果が正しいかを判断し、必要なら統合する")
    a("- 両方の結果が誤っていても、元画像から明確に読める場合は修正する")
    a("- 元画像から確定できない箇所は推測せず`unresolved`として残す")
    a("- 人間が確認すべきページ（`requires_human_review`）だけを絞り込む")
    a("")

    a("## 2. 対象情報")
    a("")
    a(f"- 対象ページ総数: {len(page_numbers)}")
    a(f"- ページ番号一覧: {page_range_text}")
    a(f"- 比較サマリー（Markdown）: `{comparison_rel}/summary.md`")
    a(f"- 比較サマリー（JSON）: `{comparison_rel}/summary.json`")
    a(
        f"- ページ別比較JSON: `{comparison_rel}/pages/page_XXX.json`"
        f"（XXXはページ番号を3桁ゼロ埋め。例: ページ{first_page} → "
        f"`page_{first_page:03d}.json`）"
    )
    a(
        "- 元画像: 各ページ別比較JSONの`source_image`フィールドの値を"
        f"`{rel_dir}/`からの相対パスとして解決する（例: `source_image`が`assets/page_"
        f"{first_page:03d}.jpeg`なら実ファイルは`{rel_dir}/assets/page_{first_page:03d}.jpeg`）"
    )
    a(f"- 候補出力先: `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/pages/page_XXX.json`（あなたが作成する）")
    a(f"- 全体集約ファイル: `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/candidates.json`（あなたが作成する）")
    a(f"- 進捗ファイル: `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/progress.json`（あなたが作成・更新する）")
    a(
        f"- 人間確認用サマリー: `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/review_summary.md`"
        "（あなたが作成する）"
    )
    a(
        f"- Apple Vision利用可否: {'利用可能' if summary.vision_helper_available else '利用不可'}"
        + (f"（{summary.vision_unavailable_reason}）" if not summary.vision_helper_available else "")
    )
    a(f"- 比較実施ページ数（両エンジンとも結果あり）: {summary.compared_pages} / {len(page_numbers)}")
    a(f"- 既存の`needs_review`ページ（Tesseract自身の判定・エンジン間不一致による要確認）: {needs_review_text}")
    a("")
    a("**OCR全文はこの指示書に埋め込まれていません。** 各ページのTesseract全文・Apple Vision全文は、")
    a("上記のページ別比較JSON（`tesseract_text`/`vision_text`フィールド）を直接読んでください。")
    a("")

    a("## 3. ページごとの確認手順")
    a("")
    a(f"対象ページ（{page_range_text}）それぞれについて、以下を順番に実行してください。")
    a("固定のバッチ件数は前提にせず、ページ数が多い場合は自分で扱いやすい単位に分けて構いません。")
    a("")
    a("1. そのページの比較JSON（`pages/page_XXX.json`）を読む")
    a("2. JSON内の`source_image`から元画像の実ファイルパスを特定し、元画像を開く")
    a("3. 元画像を実際に視覚確認する（読み飛ばさない）")
    a("4. Tesseract全文（`tesseract_text`）を確認する")
    a("5. Apple Vision全文（`vision_text`）を確認する")
    a("6. 両者の差分箇所を元画像と照合する")
    a("7. 差分箇所だけでなく、ページ全体（行順・見出し・本文・箇条書き・注記・記号・"
      "転載禁止表記等）を元画像と照合する。**両エンジンが同じ箇所を同じように誤読している")
    a("   可能性があるため、差分の無い箇所も油断しない**")
    a("8. 画像に最も忠実な`proposed_text`（ページ全体の確定候補）を作る")
    a("9. 判断内容・修正箇所を、そのページの候補JSON（6節の形式）へ保存する")
    a("10. 保存できたら次のページへ進む（全ページ確認後にまとめて保存しない。1ページごとに保存する）")
    a("")

    a("## 4. 採用判断基準")
    a("")
    a("- 元画像を唯一の正本として扱う（Tesseract・Apple Visionはいずれも参考情報）")
    a("- TesseractとApple Visionの多数決では決めない（2つのエンジンしかないため多数決は成立しない）")
    a("- 片方のエンジンが正しければ、そのページ全体でそのエンジンの結果を採用してよい")
    a("- ページ内で正しいエンジンが部分（行・段落）ごとに異なる場合は、正しい部分同士を統合する")
    a("- 両方が誤っていて、元画像から明確に読める場合は、画像に基づいて修正する")
    a("- **画像に無い文字を推測で追加しない**")
    a("- 不鮮明・欠け・極端に小さい文字等でどうしても確定できない箇所は`unresolved`として残す")
    a("- 見出し・本文・箇条書き・ページ番号・注意書き・無断転載禁止表記等、すべての要素を確認する")
    a("- 丸数字（①②…）・記号・長音（ー）・括弧・引用符・句読点・数字を省略したり安易に")
    a("  正規化（例: 丸数字を算用数字に変換する等）したりしない。元画像の見た目にできるだけ忠実にする")
    a("- 読み順、とくに2段組みや複数領域に分かれたレイアウトでの結合順序を元画像で確認する")
    a("- **元画像の意味を変えるような文章改善・言い換えはしない（OCR訂正のみを行う。教材本文の")
    a("  ブラッシュアップ・要約・言い回しの改善は今回の作業ではない）**")
    a("")

    a("## 5. 判断区分（`decision`）")
    a("")
    a("ページごとの`decision`は、次のいずれか1つに限定してください。")
    a("")
    a("- `tesseract` — ページ全体としてTesseract結果をそのまま採用")
    a("- `apple_vision` — ページ全体としてApple Vision結果をそのまま採用")
    a("- `merged` — 両エンジンの正しい部分を組み合わせた（画像に無い独自の修正は含まない）")
    a("- `corrected` — 両エンジンに無い誤りを、画像を見て修正した（部分的な統合と併用してもこちらを使う）")
    a("- `unresolved` — 1箇所以上、元画像から確定できない重要な箇所が残っている")
    a("")
    a("部分的に統合し、さらに両エンジンのどちらにも無い修正も行った場合は`corrected`を使ってください。")
    a("`unresolved_spans`が1件でもある場合、そのページの`requires_human_review`は必ず`true`にしてください。")
    a("")

    a("## 6. ページ別候補JSON仕様")
    a("")
    a(f"保存先: `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/pages/page_XXX.json`（XXXはページ番号3桁ゼロ埋め）")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "page_no": 7,')
    a('  "source_image": "assets/page_007.jpeg",')
    a('  "decision": "merged",')
    a('  "proposed_text": "元画像と照合して統合したページ全文",')
    a('  "corrections": [')
    a("    {")
    a('      "location": "本文1行目",')
    a('      "tesseract": "店労したこと",')
    a('      "apple_vision": "苦労したこと",')
    a('      "adopted": "苦労したこと",')
    a('      "reason": "元画像では「苦労」と読める"')
    a("    }")
    a("  ],")
    a('  "unresolved_spans": [],')
    a('  "requires_human_review": false,')
    a('  "review_notes": "",')
    a('  "reviewed_by": "claude_code",')
    a('  "reviewed_at": "ISO 8601"')
    a("}")
    a("```")
    a("")
    a("要件:")
    a("")
    a("- `proposed_text`はページ全体の確定候補（改行・読み順を維持する）")
    a("- `corrections`には、実際に判断した主要な差分を記録する（すべての一致箇所を列挙する必要はない）")
    a("- `reason`は元画像上の根拠を簡潔に書く")
    a("- 不明な箇所を無理に`proposed_text`へ補完しない")
    a("- `unresolved_spans`には、位置・両エンジンの読み・不明な理由を記録する。例:")
    a("")
    a("```json")
    a("{")
    a('  "location": "3行目右端",')
    a('  "tesseract": "信",')
    a('  "apple_vision": "",')
    a('  "reason": "元画像の文字が欠けており確定できない"')
    a("}")
    a("```")
    a("")
    a("- 絶対パス・秘密情報・API情報は含めない")
    a("")

    a("## 7. 進捗・中断・再開")
    a("")
    a("ページ数が多い場合（100ページ以上等）でも、1回のコンテキストへ全画像を読み込もうとしないで")
    a("ください。以下の方式で処理してください。")
    a("")
    a("- ページを順番に処理する")
    a("- 必要に応じて自分で扱いやすい単位（例: 10〜20ページごと）へ分けて進めてよい。")
    a("  固定のバッチ件数を前提にしない")
    a("- 1ページ確認するたびに、その場でページ別候補JSONを保存する（全ページ確認後にまとめて")
    a("  保存しない）")
    a("- 既に正常なページ別候補JSON（`schema_version`が正しく、対象の比較JSONより新しい）が")
    a("  存在するページは、処理済みとして扱いスキップしてよい")
    a("- 未処理のページから再開する")
    a("- 既存の候補JSONが壊れている・スキーマが不正・対象の比較JSONより古い、等の場合は")
    a("  再確認して上書きする")
    a("- 作業を中断する前に、必ず進捗ファイルを更新する")
    a("")
    a(f"進捗ファイル: `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/progress.json`")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "total_pages": 100,')
    a('  "completed_pages": [1, 2, 3],')
    a('  "unresolved_pages": [3],')
    a('  "failed_pages": [],')
    a('  "remaining_pages": [4, 5, 6],')
    a('  "updated_at": "ISO 8601"')
    a("}")
    a("```")
    a("")
    a("`remaining_pages`には、実際の全未処理ページ番号を省略せずすべて含めてください。")
    a("")

    a("## 8. 全体集約JSON")
    a("")
    a("全ページの処理が完了したら、以下を生成してください。")
    a("")
    a(f"保存先: `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/candidates.json`")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "generated_at": "ISO 8601",')
    a('  "source": "claude_code_image_review",')
    a('  "total_pages": 100,')
    a('  "completed_pages": 100,')
    a('  "requires_human_review_pages": [3, 18],')
    a('  "decision_counts": {')
    a('    "tesseract": 10,')
    a('    "apple_vision": 60,')
    a('    "merged": 20,')
    a('    "corrected": 8,')
    a('    "unresolved": 2')
    a("  },")
    a('  "pages": []')
    a("}")
    a("```")
    a("")
    a("`pages`には、ページ別候補JSONと同等の内容をページ番号順に格納してください。")
    a("")
    a("集約時に以下を検証してください（満たさない場合は先に修正してから集約する）。")
    a("")
    a("- 対象ページの欠落が無い（2節の対象ページ総数・ページ番号一覧と一致する）")
    a("- ページ番号の重複が無い")
    a("- `pages`の順序がページ番号順に正しく並んでいる")
    a("- 各ページの必須フィールドがすべて存在する")
    a(f"- `decision`が許可値（{', '.join(f'`{d}`' for d in _ALLOWED_DECISIONS)}）だけである")
    a("- `unresolved_spans`が1件以上あるページは、必ず`requires_human_review: true`になっている")
    a("- `decision_counts`の合計が完了ページ数と一致する")
    a("")

    a("## 9. 人間確認用サマリー")
    a("")
    a(f"保存先: `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/review_summary.md`")
    a("")
    a("以下を含むMarkdownを生成してください。")
    a("")
    a("- 対象ページ数")
    a("- 完了ページ数")
    a("- 判断区分（`decision`）ごとの件数")
    a("- 人間確認が必要なページ一覧（`requires_human_review`）")
    a("- ページごとの判断概要（1〜2行程度）")
    a("- 主な修正例（`corrections`から代表的なものを抜粋）")
    a("- 未解決箇所（`unresolved_spans`）の一覧")
    a("- `output/editable/lesson_pages.json`へはまだ反映されていない、という明確な注意書き")
    a("- 次に人間が行うべき操作（`requires_human_review`のページを重点的に確認する、等）")
    a("")
    a("人間はまずこのサマリーを読み、`requires_human_review_pages`のページだけを重点確認できる")
    a("ようにしてください（全ページを人間が読み直す前提にしない）。")
    a("")

    a("## 10. 完了条件")
    a("")
    a("以下をすべて満たしたときに限り、作業完了として報告してください。")
    a("")
    a("- [ ] 対象の全ページについて、ページ別候補JSONが存在する")
    a("- [ ] 全候補JSONのスキーマが6節の仕様を満たしている")
    a("- [ ] 全ページについて、実際に元画像を視覚確認している（比較JSONの文字列だけで判断していない）")
    a("- [ ] `progress.json`の`remaining_pages`が空である")
    a("- [ ] `candidates.json`が生成され、8節の検証項目をすべて満たしている")
    a("- [ ] `review_summary.md`が生成されている")
    a("- [ ] 判断不能な箇所を推測で埋めていない（`unresolved_spans`として正直に記録している）")
    a("- [ ] 人間確認が必要なページがすべて一覧化されている")
    a("- [ ] `output/editable/lesson_pages.json`を変更していない")
    a("- [ ] 比較元JSON（`summary.json`・`pages/page_XXX.json`）・元画像を変更していない")
    a("")

    a("## 11. 禁止事項（安全性の再確認）")
    a("")
    a("- Claude API・その他の外部APIを呼び出さない")
    a("- 画像やテキストを外部へ送信しない")
    a("- `output/editable/lesson_pages.json`を変更しない")
    a(f"- `{comparison_rel}/summary.json`・`{comparison_rel}/pages/`・元画像を変更しない")
    a(f"- `{comparison_rel}/{CLAUDE_REVIEW_DIR_NAME}/`配下（候補JSON・進捗・集約・サマリー）以外へ")
    a("  書き込まない")
    a("- Git commit・tag・push、ステージングは行わない（このタスクの範囲外）")
    a("")

    return "\n".join(lines) + "\n"


def write_claude_review_entry_points(output_dir: Path, summary: "ComparisonSummary") -> dict[str, Path] | None:
    """`CLAUDE_OCR_REVIEW.md`と`claude_review/README.md`を書き出す。

    Apple Visionが利用できず実質的な比較が行えなかった場合（`summary.vision_helper_available`
    が`False`）は、中身の伴わない指示書を生成して「照合できるように見せかける」ことを避けるため、
    何も書き出さず`None`を返す（呼び出し側はこの戻り値でCLI表示を分岐する）。

    `build-all`実行時点では`claude_review/README.md`以外（`pages/`・`progress.json`・
    `candidates.json`・`review_summary.md`）は生成しない（指示書を読んだClaude Codeが作成する）。
    """
    if not summary.vision_helper_available:
        return None

    comparison_dir = output_dir / "ocr_comparison"
    claude_review_dir = comparison_dir / CLAUDE_REVIEW_DIR_NAME
    claude_review_dir.mkdir(parents=True, exist_ok=True)

    instructions_path = comparison_dir / CLAUDE_OCR_REVIEW_FILENAME
    instructions_path.write_text(
        render_claude_ocr_review_instructions(summary, output_dir), encoding="utf-8"
    )

    readme_path = claude_review_dir / CLAUDE_REVIEW_README_FILENAME
    readme_path.write_text(render_claude_review_readme(), encoding="utf-8")

    return {"claude_ocr_review_md": instructions_path, "claude_review_readme": readme_path}
