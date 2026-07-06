"""
KhabriChacha — Colab Launcher

Detects Colab, loads configuration, initialises workspace + managers,
verifies the environment, launches NiceGUI, and exposes the UI.

No installation logic — run install_colab.py first.
"""

import os
import sys

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, os.path.dirname(PROJECT_ROOT))


def main():
    from loguru import logger

    print("=" * 50)
    print("  KhabriChacha — Colab Launcher")
    print("=" * 50)

    # 1. Detect environment
    import colab_utils
    if colab_utils.is_colab():
        os.environ["KHABRICHACHA_ENV"] = "colab"
        logger.info("Google Colab environment detected.")
    else:
        logger.info("Local environment detected.")

    # 2. Mount Drive (if Colab)
    if colab_utils.is_colab():
        try:
            colab_utils.mount_drive()
        except Exception as e:
            logger.error(f"Drive mount failed: {e}")
            print(f"[WARN] Google Drive mount failed: {e}")

    # 3. Load configuration
    from deployment.config_loader import load_config
    config = load_config()
    logger.info(f"Configuration loaded for environment: {os.environ.get('KHABRICHACHA_ENV', 'local')}")

    # 4. Initialise workspace
    from deployment.workspace.workspace_manager import WorkspaceManager
    workspace = WorkspaceManager(config.workspace.root)

    # 5. Initialise Project Manager
    from deployment.workspace.project_manager import ProjectManager
    project_manager = ProjectManager(workspace)
    projects = project_manager.list_projects()
    logger.info(f"Found {len(projects)} existing project(s).")

    # Check for locked projects
    for p in projects:
        if project_manager.is_locked(p.project_id):
            logger.warning(f"Project '{p.title}' ({p.project_id}) has a lock file — may need recovery.")

    # 6. Initialise Provider Manager
    from khabrichacha.providers.provider_manager import ProviderManager
    provider_manager = ProviderManager(config.to_legacy_dict())
    available = provider_manager.discover_providers_and_models()
    if available:
        logger.info(f"Available providers: {list(available.keys())}")
    else:
        logger.warning("No LLM providers configured. Research will require a provider.")

    # 7. Verify environment
    from deployment.verify_environment import run_verification
    run_verification(workspace=workspace, config=config)

    # 8. Launch NiceGUI
    from nicegui import ui
    from khabrichacha.ui.main import start_application

    start_application()

    port = config.server.port
    host = config.server.host

    # Print access URL
    if colab_utils.is_colab():
        proxy_url = colab_utils.get_colab_proxy_url(port)
        print()
        print("=" * 50)
        print(f"  KhabriChacha UI is available at:")
        print(f"  {proxy_url}")
        print("=" * 50)
        print()

    ui.run(
        title="KhabriChacha",
        host=host,
        port=port,
        reload=False,
        dark=config.server.dark,
    )


if __name__ == "__main__":
    main()
