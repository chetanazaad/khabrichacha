import os
from typing import List, Dict, Any
from loguru import logger
from deployment.workspace.workspace_manager import WorkspaceManager
from deployment.workspace.project_manager import ProjectManager

class WorkspaceIndex:
    """Indexes and searches previous project findings, assets, caches, and reports to enable local research memory."""

    def __init__(self, workspace_manager: WorkspaceManager):
        self.workspace = workspace_manager
        self.pm = ProjectManager(self.workspace)

    def search_projects(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches across all project manifests, reports, and findings for the query.
        Returns a list of matching context dictionaries.
        """
        matches = []
        STOP_WORDS = {"what", "is", "the", "of", "and", "a", "an", "in", "to", "for", "on", "with", "as", "by", "at", "from", "who", "where", "how", "why"}
        query_terms = [term.lower() for term in query.split() if len(term) > 2 and term.lower() not in STOP_WORDS]
        if not query_terms:
            return matches

        try:
            projects = self.pm.list_projects()
            for proj in projects:
                pid = proj.project_id
                title = proj.title.lower()
                mission = proj.mission.lower()
                
                # Check if non-stopword query terms overlap significantly with title or mission
                title_matches = sum(1 for term in query_terms if term in title or term in mission)
                title_match = (title_matches == len(query_terms)) if query_terms else False
                
                findings = []
                try:
                    state = self.pm.load_research_state(pid)
                    if state and state.findings:
                        findings = state.findings
                except Exception:
                    pass

                # Read report content
                report_content = ""
                report_path = os.path.join(self.workspace.projects / pid, "report.md")
                if os.path.exists(report_path):
                    try:
                        with open(report_path, "r", encoding="utf-8") as f:
                            report_content = f.read()
                    except Exception:
                        pass
                
                content_to_search = " ".join(findings).lower() + " " + report_content.lower()
                content_match_count = sum(content_to_search.count(term) for term in query_terms)
                
                if title_match or (len(query_terms) > 0 and content_match_count >= len(query_terms) * 3):
                    score = (60 if title_match else 0) + min(content_match_count * 5, 40)
                    matches.append({
                        "project_id": pid,
                        "title": proj.title,
                        "mission": proj.mission,
                        "findings": findings,
                        "report_content": report_content[:2000],  # Truncate to limit memory
                        "relevance_score": score,
                        "source_type": "workspace_project"
                    })
        except Exception as e:
            logger.error(f"Failed to search workspace index: {e}")
            
        # Sort by relevance score descending
        matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        return matches

    def search_cache(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches previous downloaded page caches in the workspace/cache folder.
        """
        matches = []
        query_terms = [term.lower() for term in query.split() if len(term) > 2]
        if not query_terms:
            return matches

        cache_dir = self.workspace.cache
        if not cache_dir.exists():
            return matches

        try:
            for item in cache_dir.iterdir():
                if item.is_file() and item.suffix == ".json":
                    try:
                        import json
                        with open(item, "r", encoding="utf-8") as f:
                            cached_data = json.load(f)
                        
                        content = cached_data.get("content", "").lower()
                        title = cached_data.get("title", "").lower()
                        url = cached_data.get("url", "")
                        
                        match_count = sum((title + " " + content).count(term) for term in query_terms)
                        if match_count > 0:
                            matches.append({
                                "url": url,
                                "title": cached_data.get("title", ""),
                                "content": cached_data.get("content", "")[:3000],
                                "relevance_score": min(match_count * 5, 100),
                                "source_type": "cache"
                            })
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Failed to search cache: {e}")
            
        matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        return matches
