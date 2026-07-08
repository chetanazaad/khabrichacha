"""
Asset Manager

Handles saving external resources (images, PDFs, HTML pages, etc.) to the local file system.
Ensures identical resources are not duplicated by hashing their contents (SHA-256).
"""

import os
import hashlib
from typing import Optional, Union


class AssetManager:
    """Manages raw assets downloaded from the web (HTML, PDF, images, etc.)."""

    def __init__(self, workspace_path: str, project_id: str):
        """
        :param workspace_path: The root directory for the workspace.
        :param project_id: The ID of the current project.
        """
        self.workspace_path = workspace_path
        self.project_id = project_id
        # We store assets inside a dedicated assets folder per project
        self.assets_dir = os.path.join(self.workspace_path, self.project_id, "assets")
        os.makedirs(self.assets_dir, exist_ok=True)

    def save_asset(self, content: Union[str, bytes], extension: str) -> str:
        """
        Save content to the assets directory if it doesn't already exist.
        Returns the absolute path to the saved asset.
        """
        # Ensure extension starts with a dot
        if not extension.startswith('.'):
            extension = f".{extension}"
            
        content_bytes = content.encode('utf-8') if isinstance(content, str) else content
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        
        filename = f"{content_hash}{extension}"
        filepath = os.path.join(self.assets_dir, filename)
        
        if not os.path.exists(filepath):
            with open(filepath, 'wb') as f:
                f.write(content_bytes)
                
        return filepath

    def get_asset_path(self, content_hash: str, extension: str) -> Optional[str]:
        """
        Check if an asset exists by its hash and extension.
        Returns the path if it exists, else None.
        """
        if not extension.startswith('.'):
            extension = f".{extension}"
            
        filename = f"{content_hash}{extension}"
        filepath = os.path.join(self.assets_dir, filename)
        
        if os.path.exists(filepath):
            return filepath
        return None
