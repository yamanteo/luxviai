from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "AI_STUDIO_CONTEXT"

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    "AI_STUDIO_CONTEXT",
}

LARGE_FILE_BYTES = 512 * 1024

TASKS = {
    "master_router_consolidation": [
        ("LUXDEEP_REPORTS/Layer34_41_Code_Gap_Closure_Master_Status.txt", "Series-wide status anchor.", "full file needed"),
        ("LUXDEEP_REPORTS/Layer34_41_Architecture_Code_Alignment_Report.txt", "Architecture/code alignment evidence.", "full file needed"),
        ("LUXDEEP_REPORTS/Smoke_Optimization_Report.txt", "Smoke timeout and optimization context.", "full file needed"),
        ("endpoint_coverage_matrix.py", "Endpoint registry alignment for Layers 37-41.", "section only: Layer 37-41 endpoint groups"),
        ("scripts/smoke_check.py", "Smoke registry and check implementation.", "section only: registry, CLI, Layer 37-41 checks"),
        ("app.py", "Import, request model, and route wiring patterns.", "section only: Layer 37-41 imports/models/routes"),
    ],
    "smoke_debug": [
        ("scripts/smoke_check.py", "Primary smoke check implementation.", "full file needed"),
        ("LUXDEEP_REPORTS/Smoke_Optimization_Report.txt", "Known smoke runtime and timeout notes.", "full file needed"),
        ("app.py", "Route/import context for failing endpoints.", "section only: imports/routes needed"),
        ("endpoint_coverage_matrix.py", "Coverage contract for endpoint checks.", "full file needed"),
    ],
    "layer_validation": [
        ("target layer modules", "Layer-specific preview modules under validation.", "section only: target layer files"),
        ("app.py", "Related imports/models/routes.", "section only: target layer wiring"),
        ("endpoint_coverage_matrix.py", "Related endpoint coverage entries.", "section only: target layer entries"),
        ("scripts/smoke_check.py", "Related smoke checks.", "section only: target layer checks"),
        ("target layer validation report", "Layer validation evidence if present.", "full file needed"),
    ],
    "router_preview_build": [
        ("app.py", "Route/model patterns for preview endpoints.", "section only: related route/model patterns"),
        ("endpoint_coverage_matrix.py", "Endpoint registration pattern.", "full file needed"),
        ("scripts/smoke_check.py", "Smoke coverage pattern.", "section only: related checks"),
        ("LUXDEEP_REPORTS/Layer34_41_Code_Gap_Closure_Master_Status.txt", "Master status context.", "full file needed"),
        ("LUXDEEP_REPORTS/Layer34_41_Architecture_Code_Alignment_Report.txt", "Architecture alignment context.", "full file needed"),
        ("latest router/consolidation plan", "Use the newest router or consolidation plan if present.", "full file needed"),
    ],
    "ui_task": [
        ("static/index.html", "Primary UI file.", "full file needed"),
        ("static/", "Relevant static CSS/JS/assets.", "section only: relevant files"),
        ("app.py", "Only if a backend route is required.", "section only: needed route"),
    ],
}


@dataclass(frozen=True)
class FileInfo:
    relative_path: str
    extension: str
    size_bytes: int
    size_kb: float
    last_modified: str
    category: str
    recommended_for: str


def is_excluded_dir(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES or "pycache" in part.lower() for part in path.parts)


def iter_project_files() -> Iterable[Path]:
    for path in sorted(ROOT.rglob("*"), key=lambda p: str(p).lower()):
        if path.is_dir():
            continue
        rel = path.relative_to(ROOT)
        if is_excluded_dir(rel.parent):
            continue
        yield path


def classify(path: Path) -> str:
    rel = path.as_posix()
    name = path.name
    if name == "app.py":
        return "app_core"
    if rel == "scripts/smoke_check.py":
        return "smoke"
    if name == "endpoint_coverage_matrix.py":
        return "endpoint_coverage"
    if rel.startswith("static/") or name in {"index.html"}:
        return "ui_static"
    if rel.startswith("LUXDEEP_REPORTS/") or name.endswith("_Report.txt") or "Report" in name:
        return "reports"
    for layer in range(37, 42):
        token = f"layer{layer}"
        if token in rel.lower() or f"_{layer}_" in rel.lower():
            return token
    if "autonomous_operations" in rel:
        return "layer41"
    if rel.startswith("agent_execution_") or rel.startswith("agent_action_") or rel.startswith("agent_task_") or rel.startswith("agent_verification_") or rel.startswith("agent_workspace_executor") or rel.startswith("agent_deployment_executor"):
        return "layer40"
    if rel.startswith("agent_runtime_") or rel.startswith("agent_session_runtime") or rel.startswith("agent_workspace_runtime") or rel.startswith("agent_memory_loop_runtime") or rel.startswith("agent_collaboration_runtime") or rel.startswith("agent_lifecycle_runtime") or rel.startswith("agent_recovery_resilience_runtime") or rel.startswith("agent_continuity_runtime"):
        return "layer39"
    if "autonomous_execution" in rel or "workflow_" in rel or "autonomous_agent_operating_model" in rel:
        return "layer38"
    if "agent" in rel and rel.endswith("_preview.py"):
        return "layer37"
    return "unknown"


def recommend(path: Path, category: str, size_bytes: int) -> str:
    rel = path.as_posix()
    if size_bytes >= LARGE_FILE_BYTES:
        return "avoid_unless_needed"
    if category == "app_core":
        return "router_consolidation"
    if category == "smoke":
        return "smoke_debug"
    if category == "endpoint_coverage":
        return "endpoint_alignment"
    if category.startswith("layer"):
        return "layer_validation"
    if category == "reports":
        return "router_consolidation"
    if category == "ui_static":
        return "ui_task"
    if rel == "scripts/build_ai_studio_context.py":
        return "ai_studio_context"
    return "avoid_unless_needed"


def collect_file_index() -> List[FileInfo]:
    rows: List[FileInfo] = []
    for path in iter_project_files():
        rel = path.relative_to(ROOT).as_posix()
        stat = path.stat()
        category = classify(Path(rel))
        rows.append(
            FileInfo(
                relative_path=rel,
                extension=path.suffix.lower(),
                size_bytes=stat.st_size,
                size_kb=round(stat.st_size / 1024, 2),
                last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                category=category,
                recommended_for=recommend(Path(rel), category, stat.st_size),
            )
        )
    return rows


def build_tree(files: List[FileInfo]) -> str:
    lines = [
        "LUXCODE PROJECT TREE FOR AI STUDIO",
        "Generated by scripts/build_ai_studio_context.py",
        "Excluded folders are omitted from this tree.",
        "",
        ".",
    ]
    emitted_dirs: set[str] = set()
    for row in files:
        parts = row.relative_path.split("/")
        for depth in range(1, len(parts)):
            directory = "/".join(parts[:depth])
            if directory not in emitted_dirs:
                emitted_dirs.add(directory)
                dir_indent = "  " * (depth - 1)
                lines.append(f"{dir_indent}- {parts[depth - 1]}/")
        indent = "  " * (len(parts) - 1)
        marker = " [LARGE]" if row.size_bytes >= LARGE_FILE_BYTES else ""
        lines.append(f"{indent}- {parts[-1]} ({row.size_kb} KB){marker}")
    return "\n".join(lines) + "\n"


def write_project_tree(files: List[FileInfo]) -> None:
    (OUTPUT_DIR / "PROJECT_TREE.txt").write_text(build_tree(files), encoding="utf-8")


def write_file_index(files: List[FileInfo]) -> None:
    with (OUTPUT_DIR / "PROJECT_FILE_INDEX.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "relative_path",
                "extension",
                "size_bytes",
                "size_kb",
                "last_modified",
                "category",
                "recommended_for",
            ],
        )
        writer.writeheader()
        for row in files:
            writer.writerow(row.__dict__)


def write_start_here() -> None:
    text = """AI STUDIO START HERE

This folder is not the whole repository. It is a compact context pack generated for Google AI Studio / Gemini.

Working rules for AI Studio:
- Ask for the exact source files or file sections before writing code.
- Do not behave as if you have live repository access.
- Do not claim that you ran tests, committed, pushed, deployed, or inspected files unless the user supplied that evidence.
- Do not enable real execution, action, write, terminal, GitHub, deployment, memory, or DB behavior.
- Keep chat, stream, WebSocket, typewriter, and durdur flows untouched unless the user explicitly asks for that scope.
- Treat static/index.html as out of scope unless the task is a UI task.
- Prefer read-only previews, static analysis, and section-specific recommendations.
- ChatGPT/Codex remains the final architecture and implementation control point for this repo.
"""
    (OUTPUT_DIR / "AI_STUDIO_START_HERE.txt").write_text(text, encoding="utf-8")


def write_task_guide() -> None:
    lines = [
        "TASK FILE SELECTION GUIDE",
        "",
        "A. master_router_consolidation",
        "- Layer34_41_Code_Gap_Closure_Master_Status.txt",
        "- Layer34_41_Architecture_Code_Alignment_Report.txt",
        "- Smoke_Optimization_Report.txt",
        "- endpoint_coverage_matrix.py only Layer 37-41 sections",
        "- scripts/smoke_check.py only registry/CLI/check sections",
        "- app.py only Layer 37-41 imports/models/routes",
        "",
        "B. smoke_debug",
        "- scripts/smoke_check.py",
        "- Smoke_Optimization_Report.txt",
        "- app.py only imports/routes needed",
        "- endpoint_coverage_matrix.py",
        "",
        "C. layer_validation",
        "- target layer modules",
        "- app.py related imports/routes",
        "- endpoint_coverage_matrix.py related entries",
        "- scripts/smoke_check.py related checks",
        "- target layer validation report",
        "",
        "D. router_preview_build",
        "- app.py related route/model patterns",
        "- endpoint_coverage_matrix.py",
        "- scripts/smoke_check.py",
        "- Layer34_41_Code_Gap_Closure_Master_Status.txt",
        "- Layer34_41_Architecture_Code_Alignment_Report.txt",
        "- latest router/consolidation plan if exists",
        "",
        "E. ui_task",
        "- static/index.html",
        "- relevant CSS/JS/static files",
        "- do not include app.py unless backend route needed",
        "",
        "F. avoid_by_default",
        "- .git",
        "- __pycache__",
        "- venv",
        "- node_modules",
        "- huge logs",
        "- old superseded reports unless historical comparison needed",
        "",
    ]
    (OUTPUT_DIR / "TASK_FILE_SELECTION_GUIDE.txt").write_text("\n".join(lines), encoding="utf-8")


def write_selected_files(task: str) -> Path:
    if task not in TASKS:
        valid = ", ".join(sorted(TASKS))
        raise SystemExit(f"Unsupported task '{task}'. Valid tasks: {valid}")
    output = OUTPUT_DIR / f"SELECTED_FILES_{task}.txt"
    lines = [
        f"SELECTED FILES FOR TASK: {task}",
        "",
        "Use this as a copy checklist for AI Studio. Prefer section-only copies when noted.",
        "",
    ]
    for path, reason, scope in TASKS[task]:
        lines.append(f"- {path}")
        lines.append(f"  reason: {reason}")
        lines.append(f"  scope: {scope}")
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def build(task: str | None = None) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    files = collect_file_index()
    write_project_tree(files)
    write_file_index(files)
    write_start_here()
    write_task_guide()
    if task:
        write_selected_files(task)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact AI Studio context files for LuxCode.")
    parser.add_argument("--task", choices=sorted(TASKS), help="Generate a task-specific selected files pack.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build(task=args.task)
    print(f"AI Studio context generated in {OUTPUT_DIR.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
