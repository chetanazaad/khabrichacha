"""
deployment/workspace/workspace_manager.py

WorkspaceManager owns the on-disk layout for the whole application:
  <root>/
    projects/   permanent, saved research projects
    temp/       ephemeral sessions (FAST/LOOKUP/STRUCTURED/etc. that the
                user hasn't explicitly saved yet)
    cache/      shared cache used by CacheManager
    assets/     shared downloaded-asset store used by AssetManager

Rebuilt after being found missing from the repo (see .gitignore fix +
project README for context) by reverse-engineering the expected
interface from every call site in deployment/runtime/research_controller.py,
khabrichacha/ui/callbacks.py, khabrichacha/ui/components.py, and
deployment/verify_environment.py.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class WorkspaceManager:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root).expanduser().resolve()
        self.projects = self.root / "projects"
        self.temp = self.root / "temp"
        self.cache = self.root / "cache"
        self.assets = self.root / "assets"

        for d in (self.root, self.projects, self.temp, self.cache, self.assets):
            d.mkdir(parents=True, exist_ok=True)

    # ── Health check ──────────────────────────────────────────

    def verify(self) -> bool:
        """Used by deployment/verify_environment.py to confirm the workspace
        is writable."""
        try:
            probe = self.root / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    # ── Path resolution ───────────────────────────────────────

    def get_project_path(self, project_id: str) -> Path:
        """Resolve a project_id to its directory, checking permanent
        projects first, then temp sessions. Returns the permanent-project
        path (creating no directory) if the project isn't found anywhere
        yet — callers that are *creating* a project should just join
        self.projects / project_id directly instead."""
        perm = self.projects / project_id
        if perm.exists():
            return perm
        tmp = self.temp / project_id
        if tmp.exists():
            return tmp
        # Fall back on naming convention if neither exists yet.
        if project_id.startswith("temp_session_"):
            return tmp
        return perm

    # ── Project accessor ──────────────────────────────────────

    def get_project(self, project_id: str) -> "ProjectManager":
        """Return a ProjectManager bound to an existing project_id, with
        its manifest and project_path already loaded."""
        from deployment.workspace.project_manager import ProjectManager
        return ProjectManager(self, project_id=project_id)
