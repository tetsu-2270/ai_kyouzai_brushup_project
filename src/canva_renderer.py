from .models import Project


def render_canva_design(project: Project) -> str:
    lines: list[str] = []
    lines.append(f"# Canva向け画像・レイアウト設計書")
    lines.append("")
    lines.append(f"元プロジェクト: {project.project_title}")
    lines.append("")
    lines.append("## 全体デザインルール")
    lines.append("- スマホ閲覧を前提に縦長レイアウトにする。")
    lines.append("- 1ページ1メッセージを原則にする。")
    lines.append("- 文字は大きめ、余白は広めに取る。")
    lines.append("- 吹き出し・人物・強調語の位置をページごとに固定しすぎず、内容に合わせて調整する。")
    lines.append("")

    for page in project.pages:
        lines.append(f"## Page {page.page_no}: {page.title}")
        lines.append("")
        lines.append(f"### レイアウト種別")
        lines.append(page.canva.layout_type or "未設定")
        lines.append("")
        lines.append("### メインビジュアル")
        lines.append(page.canva.main_visual or "未設定")
        lines.append("")
        lines.append("### 補足指示")
        lines.append(page.canva.notes or "未設定")
        lines.append("")
        lines.append("### Canva AI投入用プロンプト")
        lines.append("> 縦長SNS教材デザイン。以下の内容を、スマホで読みやすい教材ページとして作成してください。")
        lines.append(f"> タイトル: {page.title}")
        lines.append(f"> 概要: {page.summary}")
        if page.lines:
            joined = " / ".join([f"{x.speaker}: {x.text}" for x in page.lines])
            lines.append(f"> テキスト: {joined}")
        lines.append(f"> レイアウト: {page.canva.main_visual}")
        lines.append("> 文字は大きく、余白を広めに、重要語句を強調してください。")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
