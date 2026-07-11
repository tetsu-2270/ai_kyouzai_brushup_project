from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from .ocr_engine import effective_char_count, is_noise_latin_token, is_noise_symbol_token

# TesseractとApple Vision、2つの独立したOCRエンジンの結果を比較し、不一致の大きいページを
# `needs_review`へ回すための比較ロジック。
#
# 比較前に正規化するのは「改行差・連続空白・全角/半角空白」等、表示上だけの差に限定する。
# 漢字・句読点・長音・引用符・数字は安易に同一化しない（これらの差はOCR誤認識の可能性が
# あるため、比較対象として保持する）。

_WHITESPACE_RUN_RE = re.compile(r"[ \t　]+")


def normalize_for_comparison(text: str) -> str:
    """比較用の正規化。改行コードの統一・連続する半角/全角空白の圧縮・各行の前後空白除去・
    連続する空行の1行への圧縮・先頭/末尾の空行除去のみを行う。漢字・かな・句読点・長音・
    引用符・数字は変更しない（`src/ocr_engine.py`の`cleanup_whitespace()`と同様の考え方）。
    """
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized_lines = [_WHITESPACE_RUN_RE.sub(" ", line).strip() for line in lines]

    collapsed: list[str] = []
    blank_run = 0
    for line in normalized_lines:
        if not line:
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        collapsed.append(line)

    while collapsed and not collapsed[0]:
        collapsed.pop(0)
    while collapsed and not collapsed[-1]:
        collapsed.pop()
    return "\n".join(collapsed)


def _lines_of(text: str) -> list[str]:
    normalized = normalize_for_comparison(text)
    return [line for line in normalized.split("\n") if line] if normalized else []


def _title_of(text: str) -> str:
    lines = _lines_of(text)
    return lines[0] if lines else ""


def text_similarity(a: str, b: str) -> float:
    """正規化後の全文類似度（0.0〜1.0）。"""
    na, nb = normalize_for_comparison(a), normalize_for_comparison(b)
    if not na and not nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def title_similarity(a: str, b: str) -> float:
    """先頭行（タイトル行）同士の類似度（0.0〜1.0）。"""
    ta, tb = _title_of(a), _title_of(b)
    if not ta and not tb:
        return 1.0
    return difflib.SequenceMatcher(None, ta, tb).ratio()


def line_count_diff(a: str, b: str) -> int:
    return abs(len(_lines_of(a)) - len(_lines_of(b)))


def effective_char_count_diff(a: str, b: str) -> int:
    return abs(effective_char_count(normalize_for_comparison(a)) - effective_char_count(normalize_for_comparison(b)))


def edit_ratio(a: str, b: str) -> float:
    """正規化後の全文について、`difflib`の等価な挿入・削除・置換をまとめた編集比率
    （0.0=完全一致、1.0=まったく一致しない）の近似値。`1.0 - text_similarity()`として定義する。
    """
    return 1.0 - text_similarity(a, b)


@dataclass
class LineSideDiff:
    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)


def lines_only_in_one_side(a: str, b: str, *, similarity_threshold: float = 0.55) -> LineSideDiff:
    """一方の行に類似度`similarity_threshold`以上で対応する行がもう一方に無い場合、
    「一方にしか存在しない行」として集める（誤字レベルの差は許容し、行そのものが
    欠落・追加されているケースを検出するため）。
    """
    lines_a = _lines_of(a)
    lines_b = _lines_of(b)

    def _has_match(line: str, pool: list[str]) -> bool:
        return any(difflib.SequenceMatcher(None, line, other).ratio() >= similarity_threshold for other in pool)

    only_in_a = [line for line in lines_a if not _has_match(line, lines_b)]
    only_in_b = [line for line in lines_b if not _has_match(line, lines_a)]
    return LineSideDiff(only_in_a=only_in_a, only_in_b=only_in_b)


def reading_order_difference_ratio(a: str, b: str, *, similarity_threshold: float = 0.55) -> float:
    """`a`の各行を、`b`側で最も類似する未使用の行に対応付けたとき、その対応順序が
    `a`の行順と比べてどれだけ入れ替わっているか（0.0=完全に同順、1.0=最大限入れ替わっている）。

    2段組みの結合など、文字はほぼ同じでも読み順が入れ替わってしまうケースを検出するための
    近似的な指標（転倒数を理論上の最大転倒数で正規化する）。
    """
    lines_a = _lines_of(a)
    lines_b = list(_lines_of(b))
    if len(lines_a) < 2 or len(lines_b) < 2:
        return 0.0

    matched_indices: list[int] = []
    for line in lines_a:
        best_index = -1
        best_score = similarity_threshold
        for index, candidate in enumerate(lines_b):
            if candidate is None:
                continue
            score = difflib.SequenceMatcher(None, line, candidate).ratio()
            if score >= best_score:
                best_score = score
                best_index = index
        if best_index >= 0:
            matched_indices.append(best_index)
            lines_b[best_index] = None  # type: ignore[call-overload]

    n = len(matched_indices)
    if n < 2:
        return 0.0

    inversions = sum(
        1
        for i in range(n)
        for j in range(i + 1, n)
        if matched_indices[i] > matched_indices[j]
    )
    max_inversions = n * (n - 1) / 2
    return inversions / max_inversions if max_inversions else 0.0


@dataclass
class NoiseTokenDiff:
    tesseract_noise_count: int = 0
    vision_noise_count: int = 0

    @property
    def diff(self) -> int:
        return abs(self.tesseract_noise_count - self.vision_noise_count)


def _count_noise_tokens(text: str, allowed_words: set[str]) -> int:
    tokens = re.findall(r"\S+", normalize_for_comparison(text))
    return sum(1 for t in tokens if is_noise_latin_token(t, allowed_words) or is_noise_symbol_token(t))


def noise_token_diff(tesseract_text: str, vision_text: str, allowed_words: set[str]) -> NoiseTokenDiff:
    return NoiseTokenDiff(
        tesseract_noise_count=_count_noise_tokens(tesseract_text, allowed_words),
        vision_noise_count=_count_noise_tokens(vision_text, allowed_words),
    )


_JAPANESE_CHAR_RE = re.compile(
    "[぀-ゟ゠-ヿ一-鿿]"
)


def important_diff_snippets(a: str, b: str, *, min_len: int = 1, max_items: int = 20) -> list[str]:
    """正規化後の全文を文字列として比較し、置換・削除・追加された部分文字列のうち、
    一定の長さ以上かつ日本語文字を含むものを「重要語句差」として抽出する（レビュー時の
    不一致理由として提示するための、断定しない参考情報）。
    """
    na, nb = normalize_for_comparison(a), normalize_for_comparison(b)
    matcher = difflib.SequenceMatcher(None, na, nb)
    snippets: list[str] = []
    for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        candidates = [na[a_start:a_end], nb[b_start:b_end]]
        for snippet in candidates:
            stripped = snippet.strip()
            if len(stripped) < min_len:
                continue
            if not _JAPANESE_CHAR_RE.search(stripped):
                continue
            if stripped not in snippets:
                snippets.append(stripped)
            if len(snippets) >= max_items:
                return snippets
    return snippets


# --- needs_review判定（テスト可能な定数として管理） -------------------------------------------

MIN_TEXT_SIMILARITY = 0.75
MIN_TITLE_SIMILARITY = 0.85
MAX_LINE_COUNT_DIFF = 1
MAX_EFFECTIVE_CHAR_COUNT_DIFF_RATIO = 0.12
MAX_LINES_ONLY_IN_ONE_SIDE = 0
MAX_READING_ORDER_DIFF_RATIO = 0.15
MAX_NOISE_TOKEN_DIFF = 1
MAX_IMPORTANT_DIFF_SNIPPETS = 0


@dataclass
class OcrComparisonMetrics:
    text_similarity: float
    title_similarity: float
    line_count_diff: int
    effective_char_count_diff: int
    effective_char_count_diff_ratio: float
    edit_ratio: float
    lines_only_in_tesseract: list[str]
    lines_only_in_vision: list[str]
    reading_order_diff_ratio: float
    tesseract_noise_count: int
    vision_noise_count: int
    important_diff_snippets: list[str]


def compute_comparison_metrics(
    tesseract_text: str, vision_text: str, allowed_words: set[str]
) -> OcrComparisonMetrics:
    side_diff = lines_only_in_one_side(tesseract_text, vision_text)
    noise_diff = noise_token_diff(tesseract_text, vision_text, allowed_words)
    char_diff = effective_char_count_diff(tesseract_text, vision_text)
    max_chars = max(
        effective_char_count(normalize_for_comparison(tesseract_text)),
        effective_char_count(normalize_for_comparison(vision_text)),
        1,
    )
    return OcrComparisonMetrics(
        text_similarity=text_similarity(tesseract_text, vision_text),
        title_similarity=title_similarity(tesseract_text, vision_text),
        line_count_diff=line_count_diff(tesseract_text, vision_text),
        effective_char_count_diff=char_diff,
        effective_char_count_diff_ratio=char_diff / max_chars,
        edit_ratio=edit_ratio(tesseract_text, vision_text),
        lines_only_in_tesseract=side_diff.only_in_a,
        lines_only_in_vision=side_diff.only_in_b,
        reading_order_diff_ratio=reading_order_difference_ratio(tesseract_text, vision_text),
        tesseract_noise_count=noise_diff.tesseract_noise_count,
        vision_noise_count=noise_diff.vision_noise_count,
        important_diff_snippets=important_diff_snippets(tesseract_text, vision_text),
    )


def evaluate_needs_review(metrics: OcrComparisonMetrics) -> tuple[bool, list[str]]:
    """比較指標から`needs_review`かどうかを判定する。最初は保守的に、少しでも実質的な差が
    あれば人間確認へ回す（自動置換はしない）。理由は複数該当してもすべて返す。
    """
    reasons: list[str] = []

    if metrics.text_similarity < MIN_TEXT_SIMILARITY:
        reasons.append(f"全文類似度が低い（{metrics.text_similarity:.2f} < {MIN_TEXT_SIMILARITY}）")
    if metrics.title_similarity < MIN_TITLE_SIMILARITY:
        reasons.append(f"タイトルが一致しない（類似度{metrics.title_similarity:.2f} < {MIN_TITLE_SIMILARITY}）")
    if metrics.line_count_diff > MAX_LINE_COUNT_DIFF:
        reasons.append(f"行数差が大きい（{metrics.line_count_diff}行）")
    if metrics.effective_char_count_diff_ratio > MAX_EFFECTIVE_CHAR_COUNT_DIFF_RATIO:
        reasons.append(
            f"有効文字数の差が大きい（差{metrics.effective_char_count_diff}文字、"
            f"比率{metrics.effective_char_count_diff_ratio:.2f}）"
        )
    if len(metrics.lines_only_in_tesseract) > MAX_LINES_ONLY_IN_ONE_SIDE:
        reasons.append(f"Tesseractのみに存在する行がある（{len(metrics.lines_only_in_tesseract)}行）")
    if len(metrics.lines_only_in_vision) > MAX_LINES_ONLY_IN_ONE_SIDE:
        reasons.append(f"Apple Visionのみに存在する行がある（{len(metrics.lines_only_in_vision)}行）")
    if metrics.reading_order_diff_ratio > MAX_READING_ORDER_DIFF_RATIO:
        reasons.append(f"読み順の差が大きい（比率{metrics.reading_order_diff_ratio:.2f}）")
    if abs(metrics.tesseract_noise_count - metrics.vision_noise_count) > MAX_NOISE_TOKEN_DIFF:
        reasons.append(
            f"英字・記号ノイズの残存数に差がある（Tesseract {metrics.tesseract_noise_count}件 / "
            f"Apple Vision {metrics.vision_noise_count}件）"
        )
    if len(metrics.important_diff_snippets) > MAX_IMPORTANT_DIFF_SNIPPETS:
        preview = "、".join(metrics.important_diff_snippets[:3])
        reasons.append(f"重要語句に差がある（例: {preview}）")

    return (len(reasons) > 0, reasons)
