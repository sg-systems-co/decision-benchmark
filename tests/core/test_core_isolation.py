"""Core is shared by every task set: it never imports a task set and never names one."""

import ast
import re
import subprocess
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "src/decision_benchmark/core"
TASK_WORDS = re.compile(r"invoice|ap[-_]invoices|\bgst\b|\bsst\b|myinvois|peppol", re.IGNORECASE)


def core_python_files():
    files = sorted(CORE.rglob("*.py"))
    assert files
    return files


def imported_modules(path: Path) -> list[str]:
    """Absolute names of every module the file imports (relative imports resolved)."""
    package = ["decision_benchmark", *path.relative_to(CORE.parent).parent.parts]
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else []
            mod = ".".join(base + ([node.module] if node.module else []))
            names.append(mod)
            names += [f"{mod}.{a.name}" for a in node.names]
    return names


def test_core_never_imports_a_task_set():
    for path in core_python_files():
        bad = [m for m in imported_modules(path) if m.startswith("decision_benchmark.task_sets")]
        assert not bad, f"{path.relative_to(CORE)} imports {bad}"


def test_the_import_check_catches_relative_imports(tmp_path):
    probe = CORE / "_probe_for_test.py"
    probe.write_text("from ..task_sets import ap_invoices_my_sg\n", encoding="utf-8")
    try:
        assert "decision_benchmark.task_sets.ap_invoices_my_sg" in imported_modules(probe)
    finally:
        probe.unlink()


def test_importing_core_loads_no_task_set():
    code = (
        "import sys, decision_benchmark.core\n"
        "bad = [m for m in sys.modules if m.startswith('decision_benchmark.task_sets')]\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_core_does_not_name_a_task_set():
    for path in sorted(CORE.rglob("*")):
        if path.suffix in (".py", ".md"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                assert not TASK_WORDS.search(line), f"{path.relative_to(CORE)}:{n}: {line.strip()}"
