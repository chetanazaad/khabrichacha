"""
deployment/workspace/asset_manager.py

Per-project binary asset storage (downloaded PDFs, images, or any other
non-text artifact a tool wants to keep alongside a project's report).
Assets are namespaced under each project's own directory, so deleting a
project cleans up its assets automatically (see ProjectManager.delete_project).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List


class AssetManager:
    def __init__(self, workspace_manager):
        self.workspace_manager = workspace_manager

    def _assets_dir(self, project_id: str) -> Path:
        d = self.workspace_manager.get_project_path(project_id) / "assets"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _safe_name(filename: str) -> str:
        name = re.sub(r"[^A-Za-z0-9_.\-]", "_", filename)
        return name[:200] or "asset"

    def save_asset(self, project_id: str, filename: str, data: bytes) -> Path:
        path = self._assets_dir(project_id) / self._safe_name(filename)
        path.write_bytes(data)
        return path

    def get_asset_path(self, project_id: str, filename: str) -> Path:
        return self._assets_dir(project_id) / self._safe_name(filename)

    def list_assets(self, project_id: str) -> List[str]:
        d = self._assets_dir(project_id)
        if not d.exists():
            return []
        return sorted(p.name for p in d.iterdir() if p.is_file())

    def delete_asset(self, project_id: str, filename: str) -> None:
        path = self.get_asset_path(project_id, filename)
        if path.exists():
            path.unlink()
