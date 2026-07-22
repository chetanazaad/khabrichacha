"""
deployment/workspace/project_manager.py

ProjectManager handles the lifecycle of a single research project/session:
creating, resuming, listing, locking, saving, and promoting temp sessions
to permanent projects. Reconstructed from every call site across
deployment/runtime/research_controller.py, khabrichacha/ui/callbacks.py,
khabrichacha/ui/components.py, deployment/runtime/retrieval/workspace_index.py,
and the tests/ directory (see .gitignore fix / project audit for context).

Usage patterns supported (both are the same class):
  - "General purpose": ProjectManager(workspace_manager) then
    .create_project(...), .list_projects(), .save_project(project_id, ...), etc.
    None of these need any bound state.
  - "Bound to one project": ProjectManager(workspace_manager, project_id=X)
    (or workspace_manager.get_project(X)) exposes .manifest / .project_path
    and lets .load_references() be called with no arguments.

On-disk layout per project:
  <project_dir>/
    manifest.json
    report.md / report.txt / report.json / report.pdf / report.docx
    references.json
    runtime_state.json / research_state.json / planner_state.json
    logs/  cache/  references/   (created up front so tools can write into them)
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from deployment.workspace.workspace_schema import (
    ProjectManifest,
    ReferenceIndex,
    ResearchState,
)


class ProjectManager:
    def __init__(self, workspace_manager, project_id: Optional[str] = None):
        self.workspace_manager = workspace_manager
        self.project_id: Optional[str] = None
        self.manifest: Optional[ProjectManifest] = None
        self.project_path: Optional[str] = None

        if project_id:
            self._bind(project_id)

    # ── Internal helpers ──────────────────────────────────────

    def _bind(self, project_id: str) -> None:
        self.project_id = project_id
        path = self.workspace_manager.get_project_path(project_id)
        path.mkdir(parents=True, exist_ok=True)
        self.project_path = str(path)
        self.manifest = self._read_manifest(project_id)

    def _manifest_file(self, project_id: str) -> Path:
        return self.workspace_manager.get_project_path(project_id) / "manifest.json"

    def _read_manifest(self, project_id: str) -> Optional[ProjectManifest]:
        mf = self._manifest_file(project_id)
        if not mf.exists():
            return None
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
            return ProjectManifest(**data)
        except Exception:
            return None

    def _write_manifest(self, manifest: ProjectManifest) -> None:
        path = self.workspace_manager.get_project_path(manifest.project_id)
        path.mkdir(parents=True, exist_ok=True)
        mf = path / "manifest.json"
        mf.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def _new_project_id() -> str:
        return f"proj_{uuid.uuid4().hex[:12]}"

    # ── Lifecycle ─────────────────────────────────────────────

    def create_project(
        self,
        title: str,
        mission: str,
        provider: str = "",
        model: str = "",
        research_depth: str = "standard",
        is_temp: bool = False,
    ) -> ProjectManifest:
        project_id = (
            f"temp_session_{uuid.uuid4().hex[:8]}" if is_temp else self._new_project_id()
        )
        manifest = ProjectManifest(
            project_id=project_id,
            title=title,
            mission=mission,
            provider=provider,
            model=model,
            research_depth=research_depth,
            is_temp=is_temp,
            status="running",
            locked=True,
        )
        base = self.workspace_manager.temp if is_temp else self.workspace_manager.projects
        proj_dir = base / project_id
        for sub in ("logs", "cache", "references"):
            (proj_dir / sub).mkdir(parents=True, exist_ok=True)
        self._write_manifest(manifest)
        self._bind(project_id)
        return manifest

    def resume_project(self, project_id: str) -> ProjectManifest:
        manifest = self._read_manifest(project_id)
        if manifest is None:
            raise FileNotFoundError(f"Project '{project_id}' does not exist or has no manifest.")
        manifest.status = "running"
        manifest.locked = True
        self._write_manifest(manifest)
        self._bind(project_id)
        return manifest

    def list_projects(self) -> List[ProjectManifest]:
        results: List[ProjectManifest] = []
        projects_dir = self.workspace_manager.projects
        if not projects_dir.exists():
            return results
        for entry in sorted(projects_dir.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            manifest = self._read_manifest(entry.name)
            if manifest is not None:
                results.append(manifest)
        return results

    def is_locked(self, project_id: str) -> bool:
        manifest = self._read_manifest(project_id)
        return bool(manifest and manifest.locked)

    def unlock_project(self, project_id: str) -> None:
        manifest = self._read_manifest(project_id)
        if manifest is None:
            return
        manifest.locked = False
        manifest.updated_at = datetime.now()
        self._write_manifest(manifest)

    def update_manifest(self, project_id: str, **fields: Any) -> Optional[ProjectManifest]:
        manifest = self._read_manifest(project_id)
        if manifest is None:
            return None
        data = manifest.model_dump()
        data.update(fields)
        data["updated_at"] = datetime.now()
        updated = ProjectManifest(**data)
        self._write_manifest(updated)
        if self.project_id == project_id:
            self.manifest = updated
        return updated

    def delete_project(self, project_id: str) -> None:
        import shutil
        path = self.workspace_manager.get_project_path(project_id)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    def promote_session_to_project(self, temp_project_id: str) -> ProjectManifest:
        """Move a temp_session_* directory into permanent projects/ storage
        under a new permanent project_id, preserving its files."""
        import shutil

        src = self.workspace_manager.temp / temp_project_id
        if not src.exists():
            raise FileNotFoundError(f"Temporary session '{temp_project_id}' not found.")

        old_manifest = self._read_manifest(temp_project_id)
        new_id = self._new_project_id()
        dst = self.workspace_manager.projects / new_id
        shutil.copytree(src, dst)
        shutil.rmtree(src, ignore_errors=True)

        if old_manifest is not None:
            data = old_manifest.model_dump()
            data.update(project_id=new_id, is_temp=False, locked=False, updated_at=datetime.now())
            manifest = ProjectManifest(**data)
        else:
            manifest = ProjectManifest(project_id=new_id, is_temp=False, status="completed")
        self._write_manifest(manifest)
        self._bind(new_id)
        return manifest

    # ── Persistence ───────────────────────────────────────────

    def save_project(
        self,
        project_id: str,
        runtime: Any = None,
        research_state: Any = None,
        planner_state: Any = None,
        references: Optional[ReferenceIndex] = None,
        report_md: Optional[str] = None,
        report_json: Optional[Dict[str, Any]] = None,
        report_pdf_bytes: Optional[bytes] = None,
        report_docx_bytes: Optional[bytes] = None,
    ) -> None:
        path = self.workspace_manager.get_project_path(project_id)
        path.mkdir(parents=True, exist_ok=True)

        if report_md is not None:
            (path / "report.md").write_text(report_md, encoding="utf-8")
            # Plain-text copy — markdown is already readable as-is, but a
            # literal .txt satisfies "give me the output as text" without
            # anyone needing to know what a .md file is.
            (path / "report.txt").write_text(report_md, encoding="utf-8")
        if report_json is not None:
            (path / "report.json").write_text(
                json.dumps(report_json, indent=2, default=str), encoding="utf-8"
            )
        if report_pdf_bytes:
            (path / "report.pdf").write_bytes(report_pdf_bytes)
        if report_docx_bytes:
            (path / "report.docx").write_bytes(report_docx_bytes)

        if runtime is not None:
            self._dump_model(path / "runtime_state.json", runtime)
        if research_state is not None:
            self._dump_model(path / "research_state.json", research_state)
        if planner_state is not None:
            self._dump_model(path / "planner_state.json", planner_state)
        if references is not None:
            self._dump_model(path / "references.json", references)

    @staticmethod
    def _dump_model(path: Path, obj: Any) -> None:
        try:
            if hasattr(obj, "model_dump_json"):
                path.write_text(obj.model_dump_json(indent=2), encoding="utf-8")
            else:
                path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass

    # ── Loading ───────────────────────────────────────────────

    def load_references(self, project_id: Optional[str] = None) -> ReferenceIndex:
        pid = project_id or self.project_id
        if not pid:
            return ReferenceIndex()
        path = self.workspace_manager.get_project_path(pid) / "references.json"
        if not path.exists():
            return ReferenceIndex()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReferenceIndex(**data)
        except Exception:
            return ReferenceIndex()

    def load_research_state(self, project_id: Optional[str] = None) -> Optional[ResearchState]:
        pid = project_id or self.project_id
        if not pid:
            return None
        path = self.workspace_manager.get_project_path(pid) / "research_state.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ResearchState(**data)
        except Exception:
            return None
