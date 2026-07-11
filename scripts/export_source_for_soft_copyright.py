from __future__ import annotations

from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "soft_copyright"
OUTPUT_FILE = OUTPUT_DIR / "CausaLab_V1.0_源码摘录.txt"

INCLUDE_SUFFIXES = {".py", ".ts", ".vue", ".css", ".html", ".md"}
INCLUDE_DIRS = [
    ROOT / "backend" / "app",
    ROOT / "backend" / "tests",
    ROOT / "frontend" / "src",
    ROOT / "docs",
    ROOT / "scripts",
]
EXCLUDE_NAMES = {"__pycache__", ".pytest_cache", "node_modules", "dist", ".git", ".venv"}


def should_include(path: Path) -> bool:
    if path.suffix.lower() not in INCLUDE_SUFFIXES:
        return False
    return not any(part in EXCLUDE_NAMES for part in path.parts)


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for directory in INCLUDE_DIRS:
        if not directory.exists():
            continue
        files.extend(path for path in directory.rglob("*") if path.is_file() and should_include(path))
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = iter_source_files()
    lines: list[str] = [
        "CausaLab 智能实验设计与效应评估平台 V1.0 源码摘录",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"项目根目录：{ROOT}",
        f"文件数量：{len(files)}",
        "",
        "=" * 88,
        "",
    ]

    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        lines.extend([
            f"文件：{relative}",
            "-" * 88,
        ])
        try:
            lines.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            lines.append(path.read_text(encoding="utf-8-sig", errors="replace"))
        lines.extend(["", "=" * 88, ""])

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"已生成：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
