"""
Dependency Audit — Import Direction Verification

Scans import statements across the codebase and verifies:
  UI → Runtime → Core → Tools → Providers

No reverse imports are allowed (e.g., Core importing from Runtime).
Generates a markdown report.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple


LAYER_MAP: Dict[str, str] = {
    "khabrichacha.ui": "UI",
    "khabrichacha.core": "Core",
    "khabrichacha.tools": "Tools",
    "khabrichacha.providers": "Providers",
    "khabrichacha.llm": "Core",
    "deployment.runtime": "Runtime",
    "deployment.workspace": "Runtime",
    "deployment.config_loader": "Runtime",
    "deployment.reporting": "Runtime",
}

LAYER_ORDER = ["UI", "Runtime", "Core", "Tools", "Providers"]

ALLOWED_ORDER: List[Tuple[str, str]] = [
    ("UI", "Runtime"),
    ("UI", "Core"),
    ("UI", "Tools"),
    ("UI", "Providers"),
    ("Runtime", "Core"),
    ("Runtime", "Tools"),
    ("Runtime", "Providers"),
    ("Core", "Tools"),
    ("Core", "Providers"),
    ("Tools", "Providers"),
    # same-layer is always allowed
]


def _detect_layer(module_path: str) -> str:
    for prefix, layer in LAYER_MAP.items():
        if module_path.startswith(prefix):
            return layer
    return "Unknown"


def _get_relative_import(module_path: str, file_path: str, level: int) -> str:
    """Resolve a relative import like 'from ..core.session import Session'"""
    if level == 0:
        return module_path
    parts = Path(file_path).resolve().parts
    # find the package root
    pkg_parts = []
    for part in parts:
        if part == "khabrichacha" or part == "deployment":
            pkg_parts = [part]
            break
        pkg_parts.append(part)
    # go up `level` levels from the current file's package
    file_pkg_path = Path(file_path).resolve().parent
    for _ in range(level - 1):
        file_pkg_path = file_pkg_path.parent
    resolved = str(file_pkg_path).replace(os.sep, ".")
    if module_path:
        resolved = f"{resolved}.{module_path}"
    # strip drive letter on Windows
    if ":" in resolved:
        resolved = ".".join(p for p in resolved.replace(":", ".").split(".") if p and p != "\\")
    return resolved


def scan_imports(root_dir: str) -> List[Dict]:
    violations = []
    seen = set()

    for py_file in Path(root_dir).rglob("*.py"):
        # skip venv, site-packages, __pycache__
        rel = py_file.relative_to(root_dir).as_posix()
        if any(part.startswith((".", "_")) and part != "__init__.py" for part in py_file.parts):
            if "__pycache__" in py_file.parts or ".venv" in py_file.parts or "site-packages" in py_file.parts:
                continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        file_path_str = str(py_file)
        file_layer = _detect_layer(file_path_str.replace(os.sep, "."))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    key = (file_path_str, alias.name)
                    if key in seen:
                        continue
                    seen.add(key)
                    target_layer = _detect_layer(alias.name)
                    if target_layer == "Unknown" or file_layer == "Unknown":
                        continue
                    if file_layer == target_layer:
                        continue
                    if (file_layer, target_layer) not in ALLOWED_ORDER and (file_layer != target_layer):
                        violations.append({
                            "file": rel,
                            "source_layer": file_layer,
                            "target_layer": target_layer,
                            "import_stmt": f"import {alias.name}",
                        })

            elif isinstance(node, ast.ImportFrom):
                level = node.level or 0
                module = node.module or ""
                resolved_module = _get_relative_import(module, file_path_str, level) if level > 0 else module
                for alias in (node.names or []):
                    key = (file_path_str, resolved_module)
                    if key in seen:
                        continue
                    seen.add(key)
                    target_layer = _detect_layer(resolved_module)
                    if target_layer == "Unknown" or file_layer == "Unknown":
                        continue
                    if file_layer == target_layer:
                        continue
                    if (file_layer, target_layer) not in ALLOWED_ORDER:
                        violations.append({
                            "file": rel,
                            "source_layer": file_layer,
                            "target_layer": target_layer,
                            "import_stmt": f"from {module} import {alias.name}",
                        })

    return violations


def generate_report(violations: List[Dict]) -> str:
    lines = ["# Dependency Audit Report\n", f"Generated on: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    lines.append(f"**Total violations found: {len(violations)}**\n")
    if violations:
        lines.append("| # | File | Source Layer | Target Layer | Import |")
        lines.append("|---|------|-------------|-------------|--------|")
        for i, v in enumerate(violations, 1):
            lines.append(f"| {i} | `{v['file']}` | {v['source_layer']} | {v['target_layer']} | `{v['import_stmt']}` |")
    else:
        lines.append("No dependency violations found. All imports follow the allowed direction: UI → Runtime → Core → Tools → Providers.")
    return "\n".join(lines)


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    violations = scan_imports(str(repo_root))
    report = generate_report(violations)
    report_path = repo_root / "dependency_audit.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Dependency audit report written to {report_path}")
    print(f"Violations: {len(violations)}")
    for v in violations:
        print(f"  {v['file']}: {v['source_layer']} → {v['target_layer']} ({v['import_stmt']})")


if __name__ == "__main__":
    main()
