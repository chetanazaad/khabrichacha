"""
KhabriChacha — Colab Utilities

Isolated Google Colab-specific functions.
No business logic. No UI. No project management.
"""

import os
import sys
from pathlib import Path
from loguru import logger


def is_colab() -> bool:
    """Return True if running inside Google Colab."""
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False


def mount_drive() -> Path:
    """Mount Google Drive and return the root path."""
    if not is_colab():
        logger.warning("Not running in Colab — skipping Drive mount.")
        return Path(".")
    try:
        from google.colab import drive
        drive.mount("/content/drive", force_remount=False)
        root = Path("/content/drive/MyDrive")
        logger.info(f"Google Drive mounted at {root}")
        return root
    except Exception as e:
        logger.error(f"Failed to mount Google Drive: {e}")
        raise


def resolve_workspace_root() -> str:
    """Return the Colab workspace root path string."""
    if is_colab():
        return "/content/drive/MyDrive/KhabriChacha"
    return "./workspace"


def install_playwright() -> bool:
    """Install Playwright and Chromium browser inside Colab."""
    if not is_colab():
        logger.info("Not in Colab — skipping Playwright install.")
        return True
    try:
        os.system(f"{sys.executable} -m pip install playwright -q")
        os.system(f"{sys.executable} -m playwright install chromium")
        logger.info("Playwright + Chromium installed successfully.")
        return True
    except Exception as e:
        logger.error(f"Playwright installation failed: {e}")
        return False


def verify_browser() -> bool:
    """Verify Chromium is available via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        logger.info("Chromium browser verification passed.")
        return True
    except Exception as e:
        logger.warning(f"Browser verification failed: {e}")
        return False


def get_colab_proxy_url(port: int = 8080) -> str:
    """Return the Colab proxy URL for the given port."""
    if not is_colab():
        return f"http://localhost:{port}"
    try:
        from google.colab.output import eval_js
        url = eval_js(f"google.colab.kernel.proxyPort({port})")
        return str(url)
    except Exception as e:
        logger.error(f"Failed to get Colab proxy URL: {e}")
        return f"http://localhost:{port}"
