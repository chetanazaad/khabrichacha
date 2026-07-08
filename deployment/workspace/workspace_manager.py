"""
KhabriChacha — Workspace Manager

Resolves and creates every workspace directory.
All path resolution is centralised here — nothing else hardcodes paths.
"""

from pathlib import Path
from loguru import logger


class ProjectWrapper:
    def __init__(self, project_id: str, workspace_manager, project_path: Path):
        self.project_id = project_id
        self.workspace_manager = workspace_manager
        self.project_path = project_path

    @property
    def manifest(self):
        from deployment.workspace.project_manager import ProjectManager
        pm = ProjectManager(self.workspace_manager)
        return pm.load_project(self.project_id)

    def load_references(self):
        from deployment.workspace.project_manager import ProjectManager
        pm = ProjectManager(self.workspace_manager)
        return pm.load_references(self.project_id)


class WorkspaceManager:
    """
    Environment-agnostic workspace directory resolver.

    Initialised with a root directory (provided by the config loader).
    Automatically creates any missing folders on first access.
    """

    def __init__(self, root: str):
        self._root = Path(root).resolve()
        self._ensure_all()
        self._clean_old_temp_sessions()
        logger.info(f"Workspace initialised at {self._root}")

    def _clean_old_temp_sessions(self):
        """Automatically clean up temp sessions on startup."""
        try:
            import time
            import shutil
            now = time.time()
            # Clean folders in temp that are older than 2 hours or start with temp_session_
            if self.temp.exists():
                for item in self.temp.iterdir():
                    if item.is_dir() and item.name.startswith("temp_session_"):
                        mtime = item.stat().st_mtime
                        if now - mtime > 7200: # 2 hours
                            shutil.rmtree(item)
                            logger.info(f"Cleaned up old temporary session: {item.name}")
        except Exception as e:
            logger.warning(f"Failed to clean up old temp sessions: {e}")

    def get_project_path(self, project_id: str) -> Path:
        """Resolve project path, checking projects/ and temp/."""
        path = self.projects / project_id
        if not path.exists():
            temp_path = self.temp / project_id
            if temp_path.exists():
                return temp_path
        return path

    def get_project(self, project_id: str) -> ProjectWrapper:
        """Return a ProjectWrapper compatibility object."""
        path = self.get_project_path(project_id)
        return ProjectWrapper(project_id, self, path)

    # ── public path properties ───────────────────────────────

    @property
    def root(self) -> Path:
        return self._root

    @property
    def projects(self) -> Path:
        return self._root / "projects"

    @property
    def logs(self) -> Path:
        return self._root / "logs"

    @property
    def cache(self) -> Path:
        return self._root / "cache"

    @property
    def downloads(self) -> Path:
        return self._root / "downloads"

    @property
    def evidence(self) -> Path:
        return self._root / "evidence"

    @property
    def references(self) -> Path:
        return self._root / "references"

    @property
    def reports(self) -> Path:
        return self._root / "reports"

    @property
    def temp(self) -> Path:
        return self._root / "temp"

    @property
    def exports(self) -> Path:
        return self._root / "exports"

    @property
    def images(self) -> Path:
        return self._root / "images"

    @property
    def attachments(self) -> Path:
        return self._root / "attachments"

    # ── internal ─────────────────────────────────────────────

    def _ensure_all(self):
        """Create every workspace subdirectory if it does not exist."""
        dirs = [
            self.root,
            self.projects,
            self.logs,
            self.cache,
            self.downloads,
            self.evidence,
            self.references,
            self.reports,
            self.temp,
            self.exports,
            self.images,
            self.attachments,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        """Return (and create) the directory for a specific project."""
        p = self.projects / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def verify(self) -> bool:
        """Return True if every workspace folder exists and is writable."""
        for d in [self.root, self.projects, self.logs, self.cache,
                  self.downloads, self.evidence, self.references,
                  self.reports, self.temp, self.exports, self.images,
                  self.attachments]:
            if not d.exists() or not d.is_dir():
                return False
            # quick write test
            test_file = d / ".write_test"
            try:
                test_file.write_text("ok")
                test_file.unlink()
            except Exception:
                return False
        return True
