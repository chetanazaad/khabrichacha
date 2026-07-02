import json
from pathlib import Path
from khabrichacha.core.state import State
from loguru import logger

def save_session_state(state: State, storage_dir: str = "projects") -> Path:
    session_dir = Path(storage_dir) / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = session_dir / f"{state.session_id}.json"
    try:
        with open(file_path, "w") as f:
            f.write(state.model_dump_json(indent=2))
        logger.info(f"Saved session state to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save session state for {state.session_id}: {e}")
        raise e
        
    return file_path
