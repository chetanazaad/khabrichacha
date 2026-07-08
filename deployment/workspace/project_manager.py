"""
KhabriChacha — Project Manager

CRUD + lock/unlock operations for research projects.
Filesystem only — no UI, no Google Drive, no report generation.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from deployment.workspace.workspace_schema import (
    ProjectManifest,
    ProjectSettings,
    ProjectMetadata,
    RuntimeState,
    ResearchState,
    PlannerState,
    ReferenceIndex,
    EvidenceIndex,
)
from deployment.workspace.workspace_manager import WorkspaceManager


# Project sub-directories created inside every project folder
_PROJECT_SUBDIRS = [
    "logs", "evidence", "downloads", "summaries",
    "cache", "exports", "images", "attachments",
]


class ProjectManager:
    """Manages research project lifecycle on the filesystem."""

    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace
        logger.info("ProjectManager initialised.")

    # ── Create ───────────────────────────────────────────────

    def create_project(
        self,
        title: str,
        mission: str = "",
        provider: str = "",
        model: str = "",
        research_depth: str = "standard",
        is_temp: bool = False,
    ) -> ProjectManifest:
        """Create a new project directory with all required files."""
        manifest = ProjectManifest(
            title=title,
            mission=mission,
            provider=provider,
            model=model,
            research_depth=research_depth,
        )
        if is_temp:
            manifest.project_id = f"temp_session_{manifest.project_id}"
            project_dir = self.workspace.temp / manifest.project_id
            project_dir.mkdir(parents=True, exist_ok=True)
        else:
            project_dir = self.workspace.project_dir(manifest.project_id)

        # Create sub-directories based on session type
        subdirs = ["logs", "cache", "references"] if is_temp else _PROJECT_SUBDIRS
        for sub in subdirs:
            (project_dir / sub).mkdir(parents=True, exist_ok=True)

        # Write manifest
        self._write_json(project_dir / "project.json", manifest.model_dump())

        if not is_temp:

            # Write default settings
            settings = ProjectSettings(
                provider=provider,
                model=model,
                research_depth=research_depth,
            )
            self._write_json(project_dir / "project_settings.json", settings.model_dump())

            # Write empty state files
            self._write_json(project_dir / "mission.json", {"mission": mission, "title": title})
            self._write_json(project_dir / "metadata.json", ProjectMetadata().model_dump())
            self._write_json(project_dir / "runtime.json", RuntimeState().model_dump())
            self._write_json(project_dir / "research_state.json", ResearchState().model_dump())
            self._write_json(project_dir / "planner.json", PlannerState().model_dump())
            self._write_json(project_dir / "references.json", ReferenceIndex().model_dump())

            # Placeholder report files
            (project_dir / "report.md").write_text("", encoding="utf-8")
            self._write_json(project_dir / "report.json", {})

        logger.info(f"Created {'temporary ' if is_temp else ''}project '{title}' (ID: {manifest.project_id})")
        return manifest

    # ── Load ─────────────────────────────────────────────────

    def load_project(self, project_id: str) -> ProjectManifest:
        """Load and validate a project manifest."""
        project_dir = self.workspace.get_project_path(project_id)
        manifest_path = project_dir / "project.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Project '{project_id}' not found.")
        data = self._read_json(manifest_path)
        return ProjectManifest.model_validate(data)

    def load_settings(self, project_id: str) -> ProjectSettings:
        path = self.workspace.get_project_path(project_id) / "project_settings.json"
        if not path.exists():
            return ProjectSettings()
        return ProjectSettings.model_validate(self._read_json(path))

    def load_runtime(self, project_id: str) -> RuntimeState:
        path = self.workspace.get_project_path(project_id) / "runtime.json"
        if not path.exists():
            return RuntimeState()
        return RuntimeState.model_validate(self._read_json(path))

    def load_research_state(self, project_id: str) -> ResearchState:
        path = self.workspace.get_project_path(project_id) / "research_state.json"
        if not path.exists():
            return ResearchState()
        return ResearchState.model_validate(self._read_json(path))

    def load_planner_state(self, project_id: str) -> PlannerState:
        path = self.workspace.get_project_path(project_id) / "planner.json"
        if not path.exists():
            return PlannerState()
        return PlannerState.model_validate(self._read_json(path))

    def load_references(self, project_id: str) -> ReferenceIndex:
        path = self.workspace.get_project_path(project_id) / "references.json"
        if not path.exists():
            return ReferenceIndex()
        return ReferenceIndex.model_validate(self._read_json(path))

    # ── Save / Update ────────────────────────────────────────

    def save_project(
        self,
        project_id: str,
        *,
        manifest: Optional[ProjectManifest] = None,
        settings: Optional[ProjectSettings] = None,
        runtime: Optional[RuntimeState] = None,
        research_state: Optional[ResearchState] = None,
        planner_state: Optional[PlannerState] = None,
        references: Optional[ReferenceIndex] = None,
        evidence: Optional[EvidenceIndex] = None,
        report_md: Optional[str] = None,
        report_json: Optional[Dict[str, Any]] = None,
        report_pdf_bytes: Optional[bytes] = None,
        report_docx_bytes: Optional[bytes] = None,
    ) -> None:
        """Persist any provided project data files atomically."""
        project_dir = self.workspace.get_project_path(project_id)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory '{project_id}' does not exist.")

        now = datetime.now().isoformat()

        if manifest:
            manifest.updated = now
            self._write_json(project_dir / "project.json", manifest.model_dump())

        if settings:
            self._write_json(project_dir / "project_settings.json", settings.model_dump())

        if runtime:
            self._write_json(project_dir / "runtime.json", runtime.model_dump())

        if research_state:
            self._write_json(project_dir / "research_state.json", research_state.model_dump())

        if planner_state:
            self._write_json(project_dir / "planner.json", planner_state.model_dump())

        if references:
            self._write_json(project_dir / "references.json", references.model_dump())

        if evidence:
            self._write_json(project_dir / "evidence" / "evidence_index.json", evidence.model_dump())

        if report_md is not None:
            (project_dir / "report.md").write_text(report_md, encoding="utf-8")

        if report_json is not None:
            self._write_json(project_dir / "report.json", report_json)

        if report_pdf_bytes is not None:
            (project_dir / "report.pdf").write_bytes(report_pdf_bytes)

        if report_docx_bytes is not None:
            (project_dir / "report.docx").write_bytes(report_docx_bytes)

        logger.info(f"Saved project '{project_id}' at {now}")

    def update_manifest(self, project_id: str, **kwargs) -> ProjectManifest:
        """Load the manifest, update specific fields, and re-save."""
        manifest = self.load_project(project_id)
        for key, value in kwargs.items():
            if hasattr(manifest, key):
                setattr(manifest, key, value)
        manifest.updated = datetime.now().isoformat()
        project_dir = self.workspace.get_project_path(project_id)
        self._write_json(project_dir / "project.json", manifest.model_dump())
        return manifest

    # ── Delete ───────────────────────────────────────────────

    def delete_project(self, project_id: str) -> None:
        project_dir = self.workspace.get_project_path(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
            logger.info(f"Deleted project '{project_id}'")
        else:
            logger.warning(f"Project '{project_id}' not found for deletion.")

    # ── List ─────────────────────────────────────────────────

    def list_projects(self) -> List[ProjectManifest]:
        """Return all valid project manifests sorted by updated date."""
        manifests: List[ProjectManifest] = []
        for item in self.workspace.projects.iterdir():
            manifest_path = item / "project.json"
            if item.is_dir() and manifest_path.exists():
                try:
                    data = self._read_json(manifest_path)
                    manifests.append(ProjectManifest.model_validate(data))
                except Exception as e:
                    logger.warning(f"Skipping invalid project {item.name}: {e}")
        manifests.sort(key=lambda m: m.updated, reverse=True)
        return manifests

    # ── Lock / Unlock ────────────────────────────────────────

    def lock_project(self, project_id: str) -> None:
        lock_file = self.workspace.get_project_path(project_id) / "project.lock"
        lock_file.write_text(datetime.now().isoformat(), encoding="utf-8")
        self.update_manifest(project_id, status="running")
        logger.info(f"Locked project '{project_id}'")

    def unlock_project(self, project_id: str) -> None:
        lock_file = self.workspace.get_project_path(project_id) / "project.lock"
        if lock_file.exists():
            lock_file.unlink()
        logger.info(f"Unlocked project '{project_id}'")

    def is_locked(self, project_id: str) -> bool:
        lock_file = self.workspace.get_project_path(project_id) / "project.lock"
        return lock_file.exists()

    # ── Resume ───────────────────────────────────────────────

    def resume_project(self, project_id: str) -> ProjectManifest:
        """Re-load a project and re-acquire the lock."""
        manifest = self.load_project(project_id)
        # Only lock if not a temp session
        if not (self.workspace.temp / project_id).exists():
            self.lock_project(project_id)
        logger.info(f"Resumed project '{project_id}'")
        return manifest

    def promote_session_to_project(self, project_id: str) -> ProjectManifest:
        temp_dir = self.workspace.temp / project_id
        dest_dir = self.workspace.projects / project_id
        if temp_dir.exists():
            shutil.move(str(temp_dir), str(dest_dir))
            # Update manifest status to completed
            manifest = self.update_manifest(project_id, status="completed")
            logger.info(f"Promoted temporary session '{project_id}' to permanent project.")
            return manifest
        else:
            raise FileNotFoundError(f"Temporary session '{project_id}' not found.")

    # ── Export / Import ──────────────────────────────────────

    def export_project(self, project_id: str, destination: Path) -> Path:
        """Copy entire project folder to a destination directory."""
        src = self.workspace.projects / project_id
        if not src.exists():
            raise FileNotFoundError(f"Project '{project_id}' not found.")
        dest = destination / project_id
        shutil.copytree(src, dest, dirs_exist_ok=True)
        logger.info(f"Exported project '{project_id}' to {dest}")
        return dest

    def import_project(self, source: Path) -> ProjectManifest:
        """Import a project folder into the workspace."""
        manifest_path = source / "project.json"
        if not manifest_path.exists():
            raise FileNotFoundError("Source does not contain a valid project.json")
        data = self._read_json(manifest_path)
        manifest = ProjectManifest.model_validate(data)
        dest = self.workspace.projects / manifest.project_id
        shutil.copytree(source, dest, dirs_exist_ok=True)
        logger.info(f"Imported project '{manifest.title}' ({manifest.project_id})")
        return manifest

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
