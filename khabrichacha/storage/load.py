import json
from pathlib import Path
from khabrichacha.core.state import State
from loguru import logger

def load_session_state(session_id: str, storage_dir: str = "projects") -> State:
    file_path = Path(storage_dir) / "sessions" / f"{session_id}.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Session state file for '{session_id}' not found.")
        
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        logger.info(f"Loaded session state from {file_path}")
        return State.model_validate(data)
    except Exception as e:
        logger.error(f"Failed to load session state for {session_id}: {e}")
        raise e
