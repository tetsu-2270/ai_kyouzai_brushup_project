from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ocr_patterns import get_allowed_words, get_high_confidence_replacements, load_ocr_patterns

# 教材画像（大見出し・本文・グラフ・注記が混在するスライド画像）向けのOCR品質改善エンジン。
#
# `src/import_source.py`の`_try_ocr()`が画像全体をほぼ無加工のまま`pytesseract.image_to_string()`
# へ渡していたことで、本文欠落・タイトル誤認識（「だ」「YOU」等）・グラフ由来の英字ノイズ
# （`ane`/`SCRA`/`PPP`等）・辞書未登録の誤認識（`一買`/`アウトブット`/`70て80%`等）が発生していた
# 問題に対応する。個別データの手修正ではなく、同種の教材画像全般に有効な処理を目指す
# （特定画像の座標・文字列をハードコードしない）。
#
# 処理の流れ: 画像前処理の複数候補生成 → 複数PSMでのOCR（信頼度・座標付き）→ 品質スコアによる
# 最良候補選択 → 低品質な場合のみ追加前処理・領域分割での再試行 → ノイズ除去・辞書補正等の
# 後処理 → 最終テキスト+診断情報を返す。
#
# `ocr-check`/`approve-ocr-candidates`/`apply-ocr-corrections`（取り込み後のOCR崩れ診断・承認・
# 反映フロー）とは役割が異なる。このモジュールは取り込み時点でのOCR結果そのものの品質を上げる
# ものであり、画像から確定できない文章を推測して生成することはしない。辞書による自動補正も、
# 既存の`config/ocr_patterns.json`の高確信度置換（`high_confidence_replacements`）に限定する
# （それ以外の崩れは引き続き`ocr-check`以降の人間承認フローで扱う）。

_PSM_CANDIDATES: tuple[int, ...] = (6, 11)
_RETRY_PSM = 6
_LOW_CONFIDENCE_WORD_THRESHOLD = 45.0
_LOW_QUALITY_SCORE_THRESHOLD = 0.55
_MAX_UPSCALE_DIMENSION = 2400
_TITLE_BAND_HEIGHT_RATIO = 0.34
_BODY_BAND_START_RATIO = 0.22


@dataclass
class OcrWord:
    text: str
    conf: float
    left: int
    top: int
    width: int
    height: int
    block_num: int
    par_num: int
    line_num: int
    word_num: int


@dataclass
class OcrCandidate:
    words: list[OcrWord]
    preprocess: str
    psm: int
    region: str = "full"

    @property
    def text(self) -> str:
        return words_to_text(self.words)


@dataclass
class OcrDiagnostics:
    preprocess: str = ""
    psm: int = 0
    score: float = 0.0
    candidates_tried: int = 0
    retried: bool = False
    quality: str = "ok"  # "ok" または "needs_review"
    duration_seconds: float = 0.0
    region_strategy: str = "full"


@dataclass
class OcrResult:
    text: str
    diagnostics: OcrDiagnostics = field(default_factory=OcrDiagnostics)


# --- 画像前処理 -----------------------------------------------------------------------------


def generate_preprocess_variants(image: Any) -> dict[str, Any]:
    """OCR候補生成用の前処理バリエーションを返す。元の`image`オブジェクトは変更しない
    （すべて新しいImageオブジェクトとして返す）。

    - "original": 元画像相当（RGB変換のみ）。過度な前処理で細い日本語文字が欠落する場合に
      備え、常に候補として残す。
    - "enhanced": 拡大（小さい画像のみ）+ グレースケール化 + コントラスト補正 + 軽いシャープ化。
    - "binarized": "enhanced"にしきい値二値化を適用したもの。低品質時の再試行でのみ使う。
    """
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    variants: dict[str, Any] = {}
    original = image.convert("RGB")
    variants["original"] = original

    scale = 1
    if max(original.size) < _MAX_UPSCALE_DIMENSION:
        scale = 2
    resized = (
        original.resize((original.width * scale, original.height * scale), Image.LANCZOS)
        if scale > 1
        else original
    )
    gray = ImageOps.grayscale(resized)
    contrast = ImageEnhance.Contrast(gray).enhance(1.6)
    enhanced = contrast.filter(ImageFilter.SHARPEN)
    variants["enhanced"] = enhanced

    binarized = enhanced.point(lambda p: 255 if p > 180 else 0)
    variants["binarized"] = binarized

    return variants


def split_region_variants(image: Any) -> dict[str, Any]:
    """低品質時の再試行用に、一般的な横長教材スライド向けの領域分割候補を返す。

    特定画像の座標をハードコードせず、画像サイズに対する比率でのみ分割する
    （どんな横長スライド画像にも適用できる一般的なルール）。
    """
    width, height = image.size
    return {
        "top_band": image.crop((0, 0, width, int(height * _TITLE_BAND_HEIGHT_RATIO))),
        "body_band": image.crop((0, int(height * _BODY_BAND_START_RATIO), width, height)),
        "left_half": image.crop((0, 0, width // 2, height)),
        "right_half": image.crop((width // 2, 0, width, height)),
    }


# --- OCR実行（信頼度・座標付き） --------------------------------------------------------------


def _run_image_to_data(image: Any, lang: str, psm: int, tesseract_cmd: str) -> list[OcrWord]:
    import pytesseract
    from pytesseract import Output

    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    data = pytesseract.image_to_data(
        image, lang=lang, config=f"--psm {psm}", output_type=Output.DICT
    )
    words: list[OcrWord] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = data["text"][i]
        if not text or not text.strip():
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        words.append(
            OcrWord(
                text=text,
                conf=conf,
                left=int(data["left"][i]),
                top=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
                block_num=int(data["block_num"][i]),
                par_num=int(data["par_num"][i]),
                line_num=int(data["line_num"][i]),
                word_num=int(data["word_num"][i]),
            )
        )
    return words


def run_ocr_pass(
    image: Any, lang: str, psm: int, tesseract_cmd: str, preprocess: str, region: str = "full"
) -> OcrCandidate:
    words = _run_image_to_data(image, lang, psm, tesseract_cmd)
    return OcrCandidate(words=words, preprocess=preprocess, psm=psm, region=region)


def _needs_space_between(prev_text: str, next_text: str) -> bool:
    """隣接する単語の間に半角スペースを入れるべきかどうかを判定する。

    tesseractは日本語を1文字ずつ別トークンとして返すことが多く、単純にすべての単語を
    半角スペースで連結すると「【 一 貫 し た」のように文字間へ不要な空白が入ってしまう。
    両側とも日本語（かな・カナ・漢字・全角記号）の場合はスペースを入れず、それ以外
    （英数字を含む場合等）はスペースを入れる、という一般的なヒューリスティックで判定する。
    """
    if not prev_text or not next_text:
        return False
    prev_last = prev_text[-1]
    next_first = next_text[0]
    if _is_japanese_char(prev_last) and _is_japanese_char(next_first):
        return False
    return True


def words_to_text(words: list[OcrWord]) -> str:
    """単語群を、行（block_num/par_num/line_num）ごとにまとめ、行内は左から右の順に
    並べてテキストへ復元する。読み順の再構成に使う（段組み分割後の結合にも使える）。
    """
    if not words:
        return ""
    lines: dict[tuple[int, int, int], list[OcrWord]] = {}
    for w in words:
        key = (w.block_num, w.par_num, w.line_num)
        lines.setdefault(key, []).append(w)

    ordered_keys = sorted(lines.keys())
    out_lines: list[str] = []
    for key in ordered_keys:
        line_words = sorted(lines[key], key=lambda w: w.left)
        line_text = ""
        for w in line_words:
            if line_text and _needs_space_between(line_text, w.text):
                line_text += " "
            line_text += w.text
        out_lines.append(line_text.strip())
    return "\n".join(out_lines)


# --- 品質スコアの構成要素（それぞれ独立してテスト可能な小関数） ---------------------------------


def mean_confidence(words: list[OcrWord]) -> float:
    confs = [w.conf for w in words if w.conf >= 0]
    return statistics.mean(confs) if confs else 0.0


def median_confidence(words: list[OcrWord]) -> float:
    confs = [w.conf for w in words if w.conf >= 0]
    return statistics.median(confs) if confs else 0.0


def japanese_char_ratio(text: str) -> float:
    """全角ひらがな・カタカナ・漢字が、有効文字数（空白除く）に占める割合。"""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    japanese = sum(1 for c in chars if _is_japanese_char(c))
    return japanese / len(chars)


def _is_japanese_char(c: str) -> bool:
    code = ord(c)
    return (
        0x3040 <= code <= 0x309F  # ひらがな
        or 0x30A0 <= code <= 0x30FF  # カタカナ
        or 0x4E00 <= code <= 0x9FFF  # CJK統合漢字
        or 0x3000 <= code <= 0x303F  # 日本語の句読点・記号
        or 0xFF00 <= code <= 0xFFEF  # 全角英数・記号
    )


def low_confidence_word_ratio(words: list[OcrWord], threshold: float = _LOW_CONFIDENCE_WORD_THRESHOLD) -> float:
    scored = [w for w in words if w.conf >= 0]
    if not scored:
        return 0.0
    low = sum(1 for w in scored if w.conf < threshold)
    return low / len(scored)


_LATIN_TOKEN_RE = re.compile(r"[A-Za-z]+")


def is_noise_latin_token(token: str, allowed_words: set[str]) -> bool:
    """英字だけのトークンが、教材本文として自然な単語ではなく、グラフ・装飾由来のノイズ
    らしいかどうかを判定する。許可語（URL・SNS名・固有名詞・一般的な英単語等）は対象外。
    特定の文字列をハードコードせず、長さ・大文字小文字パターンだけで判定する一般的なルール。
    """
    if not token or not _LATIN_TOKEN_RE.fullmatch(token):
        return False
    if token.lower() in allowed_words:
        return False
    # 4文字以下の英字トークンは、教材本文中では固有名詞・略語であることが多く、
    # グラフ軸ラベルや装飾線の誤認識（ane/SCRA/PPP等）とも重なりやすい。
    # 5文字以上は一般的な英単語である可能性が上がるため、ノイズ扱いにしない
    # （過剰検出で正当な英字を削除しないため）。
    return len(token) <= 4


def garbled_latin_token_count(text: str, allowed_words: set[str]) -> int:
    tokens = re.findall(r"\S+", text)
    return sum(1 for t in tokens if is_noise_latin_token(t, allowed_words))


def effective_char_count(text: str) -> int:
    return len([c for c in text if not c.isspace()])


def dictionary_hit_count(text: str, high_confidence_dict: dict[str, tuple[str, str]]) -> int:
    """OCR誤認識辞書（`high_confidence_replacements`）に一致した既知の誤認識パターン数。
    多いほど、まだ辞書補正前の誤認識が残っている＝品質が低いことを示すため、スコアでは
    減点要素として扱う。
    """
    return sum(1 for wrong in high_confidence_dict if wrong in text)


def score_candidate(
    candidate: OcrCandidate,
    allowed_words: set[str],
    high_confidence_dict: dict[str, tuple[str, str]],
) -> float:
    """複数のOCR候補から最良のものを選ぶための品質スコア（大きいほど良い）。

    文字数だけで評価するとノイズの多い結果が勝ってしまうため、信頼度・日本語文字率・
    低信頼度トークン比率・英字ノイズ数・辞書一致数（誤認識の残存）をバランスさせる。
    """
    text = candidate.text
    words = candidate.words
    if not words:
        return 0.0

    conf_score = mean_confidence(words) / 100.0
    ja_ratio = japanese_char_ratio(text)
    low_conf_ratio = low_confidence_word_ratio(words)
    noise_tokens = garbled_latin_token_count(text, allowed_words)
    chars = effective_char_count(text)
    dict_hits = dictionary_hit_count(text, high_confidence_dict)
    title_line = text.split("\n", 1)[0] if text else ""
    title_penalty_value = 1.0 if is_incomplete_title_line(title_line) else 0.0

    length_score = min(chars / 150.0, 1.0)
    noise_penalty = min(noise_tokens / 6.0, 1.0)
    dict_penalty = min(dict_hits / 6.0, 1.0)

    score = (
        0.32 * conf_score
        + 0.28 * ja_ratio
        + 0.15 * length_score
        + 0.10 * (1.0 - low_conf_ratio)
        - 0.10 * noise_penalty
        - 0.05 * dict_penalty
        - 0.03 * title_penalty_value
    )
    return max(score, 0.0)


def select_best_candidate(
    candidates: list[OcrCandidate], allowed_words: set[str], high_confidence_dict: dict[str, tuple[str, str]]
) -> tuple[OcrCandidate, float]:
    scored = [(c, score_candidate(c, allowed_words, high_confidence_dict)) for c in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[0]


# --- 低品質タイトル・ノイズ行の検出 ------------------------------------------------------------


_SYMBOL_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)


def is_low_quality_title_line(line: str, allowed_words: set[str]) -> bool:
    """タイトル候補として不自然な行（一文字だけ・記号だけ・不自然な短い英字だけ）を検出する。

    特定の文字列（「だ」「YOU」等）をハードコードせず、長さ・文字種のパターンだけで判定する。
    """
    stripped = line.strip()
    if not stripped:
        return True
    if len(stripped) == 1:
        return True
    if _SYMBOL_ONLY_RE.fullmatch(stripped):
        return True
    if _LATIN_TOKEN_RE.fullmatch(stripped) and stripped.lower() not in allowed_words and len(stripped) <= 4:
        return True
    return False


# --- タイトル末尾欠落の検出・安全な補完（同一画像の別OCR候補から） -----------------------------
#
# 教材タイトルはしばしば全角括弧（【】「」『』（）等）で囲まれる。OCR候補によっては、タイトル行が
# 括弧の途中で途切れる（閉じ括弧が無い）ことがある。単に「【で始まる行に無条件で】を付ける」のでは
# 元画像に無い文字を捏造することになるため、同じページの「他のOCR候補」に、より完全なタイトルが
# 実在する場合に限って、安全条件を満たすときだけそちらを採用する。

_BRACKET_PAIRS = {"「": "」", "【": "】", "『": "』", "（": "）", "(": ")", "[": "]"}
_CLOSING_BRACKETS = set(_BRACKET_PAIRS.values())


def has_unclosed_bracket(text: str) -> bool:
    """テキストの先頭付近で開いた括弧が、閉じられないまま終わっているかどうかを判定する。

    「【一貫したキャラ」のように開き括弧はあるが閉じ括弧が無いタイトル行を検出するための、
    一般的な（特定文字列に依存しない）シグナル。閉じ括弧だけが単独である場合はここでは
    対象にしない（開き括弧が無いのに閉じ括弧だけがあるのは別の崩れ方であり、本関数の目的外）。
    """
    stack: list[str] = []
    for ch in text:
        if ch in _BRACKET_PAIRS:
            stack.append(_BRACKET_PAIRS[ch])
        elif ch in _CLOSING_BRACKETS and stack and ch == stack[-1]:
            stack.pop()
    return bool(stack)


def is_incomplete_title_line(line: str) -> bool:
    """タイトル行が途中で欠落している疑いがあるかどうかを判定する（閉じ括弧の欠落を主な兆候とする）。"""
    stripped = line.strip()
    if not stripped:
        return False
    return has_unclosed_bracket(stripped)


_TITLE_UNCERTAIN_CONFIDENCE = 15.0


def _first_line_words(words: list[OcrWord]) -> list[OcrWord]:
    """`words`のうち、読み順で最初の行（block_num/par_num/line_numが最小の行）に属する単語だけを、
    左から右の順で返す。"""
    if not words:
        return []
    lines: dict[tuple[int, int, int], list[OcrWord]] = {}
    for w in words:
        key = (w.block_num, w.par_num, w.line_num)
        lines.setdefault(key, []).append(w)
    if not lines:
        return []
    first_key = min(lines.keys())
    return sorted(lines[first_key], key=lambda w: w.left)


def title_line_min_confidence(candidate: OcrCandidate) -> float:
    """候補の先頭行（タイトル行）に含まれる単語のうち、最も低い信頼度を返す。単語が無い場合は
    100.0（＝疑わしい要素なし）を返す。値が極端に低い場合、タイトル行のどこかに強く疑わしい
    文字（誤読・ノイズ）が含まれている可能性が高いことを示す一般的なシグナルとして使う。
    """
    words = _first_line_words(candidate.words)
    confs = [w.conf for w in words if w.conf >= 0]
    return min(confs) if confs else 100.0


def title_is_uncertain(candidate: OcrCandidate, threshold: float = _TITLE_UNCERTAIN_CONFIDENCE) -> bool:
    """タイトル行に、極端に信頼度の低い（＝tesseract自身が強く疑わしいと判定している）
    文字・トークンが含まれているかどうかを判定する。"""
    return title_line_min_confidence(candidate) < threshold


def title_similarity(a: str, b: str) -> float:
    """2つのタイトル候補文字列の類似度（0.0〜1.0）。`difflib`による一般的な類似度計算で、
    「一買」/「一貫」のような1文字だけのOCR誤認識の違いを許容しつつ、まったく無関係な
    文字列（本文の別の行等）とは区別できるようにする。
    """
    import difflib

    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _common_prefix_length(a: str, b: str) -> int:
    length = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        length += 1
    return length


def find_more_complete_title(
    current_title: str,
    candidate_titles: list[tuple[str, float]],
    allowed_words: set[str],
    *,
    current_score: float,
    current_uncertain: bool = False,
    min_similarity: float = 0.6,
    min_score_ratio: float = 0.6,
) -> str | None:
    """現在のタイトル行より安全に「より完全」と判断できる候補があれば、その文字列を返す。
    無ければ`None`を返す（元画像に無い文字を推測で追加しない）。

    `candidate_titles`は`(タイトル候補の文字列, その候補全体の品質スコア)`のリスト。
    以下をすべて満たす候補だけを採用対象にする。

    - 低品質タイトル行（`is_low_quality_title_line`）ではない
    - `current_title`より文字数が長い。ただし`current_uncertain=True`（現在のタイトル行に
      極端に信頼度の低い文字が含まれる）の場合に限り、同じ長さの候補も対象にする
      （例: 「一買」→「一貫」のような1文字だけの高確信度辞書補正で、文字数が変わらないまま
      より確からしいタイトルへ差し替えられるようにするため）
    - 候補の品質スコアが、現在のスコアに対して十分高い（`min_score_ratio`以上の比率）
    - `current_title`との共通接頭辞が半分以上、または全体の類似度が`min_similarity`以上
    - 英字ノイズを現在より増やさない
    - 現在のタイトルが閉じ括弧欠落なのに、候補も閉じ括弧欠落のままでは改善にならないため除外
    - 現在のタイトルが構造的に途中欠落（閉じ括弧欠落）でも極端に低信頼度でもない場合は、
      そもそも候補を一切採用しない（すでに正常なタイトルを、たまたま類似・長めの
      本文行等で誤って上書きしないため）
    """
    if not current_title:
        return None

    current_unclosed = has_unclosed_bracket(current_title)
    if not (current_unclosed or current_uncertain):
        return None

    current_noise = garbled_latin_token_count(current_title, allowed_words)

    best_replacement: str | None = None
    best_length = len(current_title)

    for title_line, score in candidate_titles:
        if not title_line or title_line == current_title:
            continue
        if is_low_quality_title_line(title_line, allowed_words):
            continue
        if len(title_line) < best_length:
            continue
        if len(title_line) == best_length and not current_uncertain:
            continue
        if current_score > 0 and score < current_score * min_score_ratio:
            continue

        similarity = title_similarity(current_title, title_line)
        prefix_len = _common_prefix_length(current_title, title_line)
        prefix_ratio = prefix_len / len(current_title) if current_title else 0.0
        if not (similarity >= min_similarity or prefix_ratio >= 0.5):
            continue

        if garbled_latin_token_count(title_line, allowed_words) > current_noise:
            continue

        if current_unclosed and has_unclosed_bracket(title_line):
            continue

        best_replacement = title_line
        best_length = len(title_line)

    return best_replacement


def complete_title_in_text(
    text: str,
    sibling_titles: list[tuple[str, float]],
    allowed_words: set[str],
    *,
    current_score: float,
    current_uncertain: bool = False,
) -> str:
    """テキストの先頭行（タイトル行）を、条件を満たす場合だけ、より完全な兄弟候補へ差し替える。
    先頭行以外（本文）は変更しない。差し替え対象が見つからない場合は元のテキストをそのまま返す。
    """
    if not text:
        return text
    lines = text.split("\n")
    current_title = lines[0]
    replacement = find_more_complete_title(
        current_title,
        sibling_titles,
        allowed_words,
        current_score=current_score,
        current_uncertain=current_uncertain,
    )
    if replacement is None:
        return text
    lines[0] = replacement
    return "\n".join(lines)


# --- 後処理（ノイズ除去・辞書補正） ------------------------------------------------------------


_WAVE_DASH_MISREAD_RE = re.compile(r"(\d)\s*て\s*(\d)")


def fix_wave_dash_misread(text: str) -> str:
    """`70て80%`のような「〜」の誤認識（数字-て-数字）を`70〜80%`へ補正する。

    tesseractが波ダッシュ「〜」をひらがな「て」と誤認識する既知のパターンに対応する
    一般的な補正（特定の数値の組み合わせに限定しない）。
    """
    return _WAVE_DASH_MISREAD_RE.sub(r"\1〜\2", text)


def apply_high_confidence_fixes(text: str, high_confidence_dict: dict[str, tuple[str, str]]) -> str:
    """`config/ocr_patterns.json`の高確信度置換（`high_confidence_replacements`）だけを
    自動適用する。それ以外のOCR崩れは、引き続き`ocr-check`以降の人間承認フローで扱う。
    """
    for wrong, (suggested, _severity) in high_confidence_dict.items():
        if suggested:
            text = text.replace(wrong, suggested)
    return text


def is_noise_symbol_token(token: str) -> bool:
    """記号だけの短いトークン（装飾線・句読点の誤認識等）かどうかを判定する。
    低信頼度と組み合わせたときだけノイズ扱いにする（`filter_noise_words`参照）。
    """
    if not token:
        return False
    return bool(_SYMBOL_ONLY_RE.fullmatch(token)) and len(token) <= 2


def filter_noise_words(
    words: list[OcrWord], allowed_words: set[str], confidence_threshold: float = _LOW_CONFIDENCE_WORD_THRESHOLD
) -> list[OcrWord]:
    """低信頼度の英字ノイズ（グラフ・装飾由来）・低信頼度の孤立した記号を除外する。正当な英字・
    URL・固有名詞・許可語・日本語トークンは対象外（一律削除しない）。
    """
    kept: list[OcrWord] = []
    for w in words:
        text = w.text.strip()
        if not text:
            continue
        is_noise = is_noise_latin_token(text, allowed_words) or is_noise_symbol_token(text)
        if is_noise and w.conf >= 0 and w.conf < confidence_threshold:
            continue
        kept.append(w)
    return kept


def cleanup_whitespace(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned: list[str] = []
    blank_run = 0
    for line in lines:
        if not line.strip():
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        cleaned.append(line)
    return "\n".join(cleaned).strip("\n")


def postprocess_candidate(
    candidate: OcrCandidate,
    allowed_words: set[str],
    high_confidence_dict: dict[str, tuple[str, str]],
) -> str:
    """最終選択されたOCR候補に対し、ノイズ除去・不自然な先頭/末尾行の除去・辞書補正・
    波ダッシュ誤認識補正・空白整理を適用する。"""
    filtered_words = filter_noise_words(candidate.words, allowed_words)
    text = words_to_text(filtered_words)

    lines = text.split("\n")
    while lines and is_low_quality_title_line(lines[0], allowed_words):
        lines.pop(0)
    # 末尾に孤立した一文字・記号だけの行が残ることがある（装飾線・ノイズの誤認識）ため、
    # 先頭行と同じ基準で末尾も除去する。ただし本文が無くなるほどは削らない。
    while len(lines) > 1 and is_low_quality_title_line(lines[-1], allowed_words):
        lines.pop()
    text = "\n".join(lines)

    text = apply_high_confidence_fixes(text, high_confidence_dict)
    text = fix_wave_dash_misread(text)
    text = cleanup_whitespace(text)
    return text


# --- 領域分割結果の結合（段組み・タイトル/本文分割の読み順再構成） --------------------------------


def _offset_block_numbers(words: list[OcrWord], offset: int) -> list[OcrWord]:
    """`block_num`へ`offset`を加えた新しい`OcrWord`のリストを返す（元のリストは変更しない）。"""
    return [
        OcrWord(
            text=w.text,
            conf=w.conf,
            left=w.left,
            top=w.top,
            width=w.width,
            height=w.height,
            block_num=w.block_num + offset,
            par_num=w.par_num,
            line_num=w.line_num,
            word_num=w.word_num,
        )
        for w in words
    ]


_REGION_BLOCK_OFFSET_STEP = 10000


def combine_region_words(regions: list[list[OcrWord]]) -> list[OcrWord]:
    """複数領域（例: タイトル帯→本文帯、左カラム→右カラム）のOCR結果（`words`）を、
    指定した順序を保ったまま1つの単語リストへ結合する。

    各領域は独立した画像（クロップ）に対してOCRしているため、`block_num`/`par_num`/`line_num`は
    領域ごとに1から採番され直す。単純に単語リストを連結すると、異なる領域の行が同じ
    `(block_num, par_num, line_num)`キーに衝突し、`words_to_text()`が別領域の単語を同じ行として
    扱ってしまう（読み順が混ざる）。領域ごとに`block_num`へ大きなオフセットを与えることで、
    `words_to_text()`のソート順（block_num優先）で領域順が保たれ、かつ衝突しないようにする。
    """
    combined: list[OcrWord] = []
    for index, region_words in enumerate(regions):
        combined.extend(_offset_block_numbers(region_words, index * _REGION_BLOCK_OFFSET_STEP))
    return combined


def combine_region_candidates(regions: list[tuple[str, OcrCandidate]], region_label: str = "combined") -> OcrCandidate:
    """複数の領域（例: 左カラム→右カラム、タイトル帯→本文帯）のOCR結果を、指定した順序を
    維持したまま1つの`OcrCandidate`へ統合する。

    単語（信頼度・座標付き）を保持したまま統合するため、統合結果を`score_candidate()`や
    `postprocess_candidate()`にそのまま渡せる（`run_multi_ocr()`の実処理と一致させるため。
    単純に`.text`を文字列連結すると単語単位の信頼度情報が失われ、品質評価に使えなくなる）。
    """
    region_words = [candidate.words for _name, candidate in regions]
    combined_words = combine_region_words(region_words)
    preprocess = regions[0][1].preprocess if regions else ""
    psm = regions[0][1].psm if regions else 0
    return OcrCandidate(words=combined_words, preprocess=preprocess, psm=psm, region=region_label)


# --- トップレベルのオーケストレーション --------------------------------------------------------


def _sibling_title_candidates(
    pool: list[OcrCandidate],
    exclude: OcrCandidate,
    allowed_words: set[str],
    high_confidence_dict: dict[str, tuple[str, str]],
) -> list[tuple[str, float]]:
    """`pool`内の`exclude`以外の各候補について、後処理済みテキストの先頭行（タイトル候補）と
    その候補の品質スコアの組を返す。タイトル補完（`find_more_complete_title`）の入力に使う。
    """
    result: list[tuple[str, float]] = []
    for cand in pool:
        if cand is exclude:
            continue
        text = postprocess_candidate(cand, allowed_words, high_confidence_dict)
        if not text:
            continue
        first_line = text.split("\n", 1)[0]
        score = score_candidate(cand, allowed_words, high_confidence_dict)
        result.append((first_line, score))
    return result


def run_multi_ocr(
    image_path: str | Path,
    ocr_status: dict[str, Any],
    lang: str,
    tesseract_cmd: str,
    *,
    patterns: dict[str, Any] | None = None,
) -> OcrResult:
    """教材画像1枚に対し、複数の前処理・PSM候補からOCRし、品質スコアで最良候補を選び、
    低品質な場合のみ追加の前処理・領域分割で再試行したうえで、後処理済みテキストを返す。

    タイトル行（先頭行）が閉じ括弧欠落等で途中欠落している疑いがある場合、同じ画像から得た
    他のOCR候補（`candidates`、再試行時は`retry_candidates`）に、より完全で安全に採用できる
    タイトルがあれば差し替える（`find_more_complete_title`参照）。元画像に無い文字を推測で
    追加することはしない。
    """
    import time

    from PIL import Image

    started = time.monotonic()

    if patterns is None:
        patterns, _meta = load_ocr_patterns()
    allowed_words = get_allowed_words(patterns)
    high_confidence_dict = get_high_confidence_replacements(patterns)

    with Image.open(image_path) as raw_image:
        image = raw_image.convert("RGB")
        image.load()

    variants = generate_preprocess_variants(image)

    candidates: list[OcrCandidate] = []
    for preprocess_name in ("original", "enhanced"):
        variant_image = variants[preprocess_name]
        for psm in _PSM_CANDIDATES:
            candidates.append(run_ocr_pass(variant_image, lang, psm, tesseract_cmd, preprocess_name))

    def _own_title_line(candidate: OcrCandidate) -> str:
        text = postprocess_candidate(candidate, allowed_words, high_confidence_dict)
        return text.split("\n", 1)[0] if text else ""

    best_candidate, best_score = select_best_candidate(candidates, allowed_words, high_confidence_dict)
    final_text = postprocess_candidate(best_candidate, allowed_words, high_confidence_dict)

    title_uncertain = title_is_uncertain(best_candidate)
    sibling_titles = _sibling_title_candidates(candidates, best_candidate, allowed_words, high_confidence_dict)
    final_text = complete_title_in_text(
        final_text, sibling_titles, allowed_words, current_score=best_score, current_uncertain=title_uncertain
    )
    title_line = final_text.split("\n", 1)[0] if final_text else ""
    title_changed = title_line != _own_title_line(best_candidate)
    title_incomplete = is_incomplete_title_line(title_line)

    retried = False
    region_strategy = "full"

    # 通常のスコア閾値に加え、以下のいずれかに該当する場合だけ、追加のOCR（二値化・領域分割）で
    # 再試行する。スコアが十分でもタイトルだけ問題がある教材ページに対応するための、的を絞った
    # 追加条件（一律の閾値変更や常時再試行ではない）。
    # - タイトルが途中欠落したまま（同一候補プール内での安全な補完でも解消できなかった）
    # - タイトル行に極端に信頼度の低い文字が残ったまま（かつ補完でも解消できなかった）
    needs_retry_for_title = title_incomplete or (title_uncertain and not title_changed)
    if best_score < _LOW_QUALITY_SCORE_THRESHOLD or needs_retry_for_title:
        retried = True
        retry_candidates = list(candidates)

        binarized_candidate = run_ocr_pass(
            variants["binarized"], lang, _RETRY_PSM, tesseract_cmd, "binarized"
        )
        retry_candidates.append(binarized_candidate)

        regions = split_region_variants(variants["enhanced"])

        top_band_candidate = run_ocr_pass(
            regions["top_band"], lang, _RETRY_PSM, tesseract_cmd, "enhanced", region="top_band"
        )
        body_band_candidate = run_ocr_pass(
            regions["body_band"], lang, _RETRY_PSM, tesseract_cmd, "enhanced", region="body_band"
        )
        band_combined = combine_region_candidates(
            [("top_band", top_band_candidate), ("body_band", body_band_candidate)],
            region_label="top_body_split",
        )
        retry_candidates.append(band_combined)

        left_candidate = run_ocr_pass(
            regions["left_half"], lang, _RETRY_PSM, tesseract_cmd, "enhanced", region="left_half"
        )
        right_candidate = run_ocr_pass(
            regions["right_half"], lang, _RETRY_PSM, tesseract_cmd, "enhanced", region="right_half"
        )
        column_combined = combine_region_candidates(
            [("left_half", left_candidate), ("right_half", right_candidate)],
            region_label="left_right_split",
        )
        retry_candidates.append(column_combined)

        new_best, new_score = select_best_candidate(retry_candidates, allowed_words, high_confidence_dict)
        if new_score > best_score:
            best_candidate, best_score = new_best, new_score
            region_strategy = best_candidate.region
            final_text = postprocess_candidate(best_candidate, allowed_words, high_confidence_dict)

        title_uncertain = title_is_uncertain(best_candidate)

        # タイトル補完は、本文候補（best_candidate）の選び直しとは独立に、再試行で新たに得られた
        # 候補（タイトル帯専用のtop_band_candidateを含む）もあわせて再度試みる。
        retry_sibling_titles = _sibling_title_candidates(
            retry_candidates + [top_band_candidate], best_candidate, allowed_words, high_confidence_dict
        )
        final_text = complete_title_in_text(
            final_text,
            retry_sibling_titles,
            allowed_words,
            current_score=best_score,
            current_uncertain=title_uncertain,
        )
        title_line = final_text.split("\n", 1)[0] if final_text else ""
        title_changed = title_line != _own_title_line(best_candidate)
        title_incomplete = is_incomplete_title_line(title_line)

    # 品質判定は、再試行の有無に関わらず「最終的にタイトルが構造的に欠落したままか」
    # 「信頼度が低いまま補完もされなかったか」という最終状態でのみ行う（再試行前に立てた
    # トリガーをそのまま引きずらない。再試行でタイトルが正しく補完されたページを
    # 誤ってneeds_reviewのままにしないため）。
    title_still_problematic = title_incomplete or (title_uncertain and not title_changed)
    quality = (
        "ok"
        if (best_score >= _LOW_QUALITY_SCORE_THRESHOLD and not title_still_problematic)
        else "needs_review"
    )

    diagnostics = OcrDiagnostics(
        preprocess=best_candidate.preprocess,
        psm=best_candidate.psm,
        score=round(best_score, 4),
        candidates_tried=len(candidates) + (5 if retried else 0),
        retried=retried,
        quality=quality,
        duration_seconds=round(time.monotonic() - started, 3),
        region_strategy=region_strategy,
    )
    return OcrResult(text=final_text, diagnostics=diagnostics)
