"""
KhabriChacha — Colab Installer

Installs requirements, Playwright, Chromium, and verifies the result.
This script should be run ONCE before launch_colab.py.
"""

import subprocess
import sys
import os
from pathlib import Path


def _run(cmd: str, label: str) -> bool:
    print(f"[INSTALL] {label}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [PASS] {label}")
        return True
    else:
        print(f"  [FAIL] {label}")
        if result.stderr:
            print(f"         {result.stderr[:200]}")
        return False


def install():
    project_root = Path(__file__).resolve().parent.parent
    requirements = project_root / "requirements.txt"

    all_passed = True

    # 1. Upgrade pip
    all_passed &= _run(
        f"{sys.executable} -m pip install --upgrade pip -q",
        "Upgrade pip",
    )

    # 2. Install requirements
    if requirements.exists():
        all_passed &= _run(
            f"{sys.executable} -m pip install -r {requirements} -q",
            "Install requirements.txt",
        )
    else:
        print(f"  [WARN] requirements.txt not found at {requirements}")

    # 3. Install reportlab (PDF generation)
    all_passed &= _run(
        f"{sys.executable} -m pip install reportlab -q",
        "Install reportlab",
    )

    # 4. Install Playwright
    all_passed &= _run(
        f"{sys.executable} -m pip install playwright -q",
        "Install Playwright",
    )

    # 5. Install Chromium via Playwright
    all_passed &= _run(
        f"{sys.executable} -m playwright install chromium",
        "Install Chromium browser",
    )

    # Final result
    print()
    if all_passed:
        print("=" * 50)
        print("  INSTALLATION: PASS")
        print("=" * 50)
    else:
        print("=" * 50)
        print("  INSTALLATION: FAIL (some steps had errors)")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    install()
