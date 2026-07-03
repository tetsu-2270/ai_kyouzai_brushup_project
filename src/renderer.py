from .models import Project


def render_brushup(project: Project) -> str:
    lines: list[str] = []
    lines.append(f"# {project.project_title}")
    lines.append("")
    lines.append(f"対象読者: {project.target_reader}")
    lines.append("")
    lines.append("## 全体方針")
    lines.append("- ページ単位で情報を整理する。")
    lines.append("- 話者ごとに台詞を分ける。")
    lines.append("- 教材として理解しやすい順序・表現に整える。")
    lines.append("")

    for page in project.pages:
        lines.append(f"## Page {page.page_no}: {page.title}")
        lines.append("")
        lines.append(f"元画像: `{page.source_image}`")
        lines.append("")
        lines.append("### 概要")
        lines.append(page.summary or "未設定")
        lines.append("")
        lines.append("### 文字起こし")
        for item in page.lines:
            lines.append(f"- **{item.speaker}**: {item.text}")
        lines.append("")
        lines.append("### 改善ポイント")
        if page.improvement_points:
            for point in page.improvement_points:
                lines.append(f"- {point}")
        else:
            lines.append("- 未設定")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
