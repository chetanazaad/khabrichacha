import json
from typing import List, Dict, Any
from pathlib import Path
from loguru import logger

class ProjectManager:
    def __init__(self, projects_dir: str = "projects"):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        project_id = name.lower().replace(" ", "_").strip()
        project_path = self.projects_dir / f"{project_id}.json"
        
        project_data = {
            "id": project_id,
            "name": name,
            "description": description,
            "sessions": []
        }
        
        try:
            with open(project_path, "w") as f:
                json.dump(project_data, f, indent=2)
            logger.info(f"Created project {name} (ID: {project_id})")
        except Exception as e:
            logger.error(f"Failed to create project file: {e}")
            raise e
            
        return project_data

    def list_projects(self) -> List[Dict[str, Any]]:
        projects = []
        for file in self.projects_dir.glob("*.json"):
            try:
                with open(file, "r") as f:
                    projects.append(json.load(f))
            except Exception as e:
                logger.error(f"Failed to load project {file.name}: {e}")
        return projects

    def get_project(self, project_id: str) -> Dict[str, Any]:
        project_path = self.projects_dir / f"{project_id}.json"
        if not project_path.exists():
            raise FileNotFoundError(f"Project '{project_id}' not found.")
            
        with open(project_path, "r") as f:
            return json.load(f)

    def add_session_to_project(self, project_id: str, session_id: str):
        try:
            project_data = self.get_project(project_id)
            if session_id not in project_data.get("sessions", []):
                project_data.setdefault("sessions", []).append(session_id)
                project_path = self.projects_dir / f"{project_id}.json"
                with open(project_path, "w") as f:
                    json.dump(project_data, f, indent=2)
                logger.info(f"Added session {session_id} to project {project_id}")
        except Exception as e:
            logger.error(f"Failed to add session {session_id} to project {project_id}: {e}")
