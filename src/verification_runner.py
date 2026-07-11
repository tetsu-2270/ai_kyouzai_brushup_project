from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .verification_evidence import EvidenceRun, check_acceptance_files, parse_junit_summary

# `scripts/run_verification.sh`から呼ばれる、正式な検証入口のCLI本体。
# 標準実行は「pytest -q --junitxml」→「scripts/run_sample.sh」の順で実行し、
# 結果をlogs/evidence/<run_id>/へ保存する（詳細はREADME/docs/04_output_spec.md参照）。
#
# 片方が失敗しても、もう片方は続けて実行する（失敗を記録したうえで残りも実行し、
# 最終的な終了コードは非ゼロにする方式）。

# run_sample.shが生成することを期待する主要ファイル（サンプルデータ由来。実教材ではない）。
_ACCEPTANCE_FILES = [
    "output/lesson_pages.json",
    "output/brushup.md",
    "output/canva_design.md",
    "output/brushup.docx",
    "output/brushup.pdf",
    "output/scenario/scenario.json",
    "output/scenario/scenario.md",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_standard_verification(purpose: str = "standard verification (pytest + run_sample.sh)") -> int:
    project_root = _project_root()
    run = EvidenceRun(purpose=purpose, project_root=project_root)

    try:
        junit_path = run.run_dir / "pytest" / "junit.xml"
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        pytest_record = run.run_command(
            "pytest",
            [sys.executable, "-m", "pytest", "-q", f"--junitxml={junit_path}"],
            extra_artifacts=[junit_path],
        )
        pytest_summary = parse_junit_summary(junit_path)
        if pytest_summary:
            pytest_record.extra["pytest_summary"] = pytest_summary

        run_sample_path = project_root / "scripts" / "run_sample.sh"
        run_sample_record = run.run_command(
            "run_sample",
            ["bash", str(run_sample_path)],
        )
        acceptance = check_acceptance_files(
            [project_root / p for p in _ACCEPTANCE_FILES], run_dir=run.run_dir
        )
        run_sample_record.extra["acceptance_checks"] = acceptance
    except KeyboardInterrupt:
        # run_command()側で既にfinalize(interrupted)済み。
        return 130

    manifest = run.finalize()
    print(f"evidence: {run.run_dir}")
    print(f"overall_status: {manifest['overall_status']}")
    return manifest["overall_exit_code"]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="pytest/run_sample.shの検証結果をlogs/evidence/へ永続保存する正式な検証入口"
    )
    parser.add_argument(
        "--purpose", default="standard verification (pytest + run_sample.sh)", help="この実行の目的（summary.mdに記録）"
    )
    args = parser.parse_args(argv)

    exit_code = run_standard_verification(purpose=args.purpose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
