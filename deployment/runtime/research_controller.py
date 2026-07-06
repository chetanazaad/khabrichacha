"""
Research Controller

The single entry point for starting a research task. It bridges the gap between
the UI (or CLI/API) and the core engine. It orchestrates the lifecycle:
Project Creation -> Provider Validation -> Tool Execution -> Orchestration -> Reporting.
"""

import os
import time
from typing import Dict, Any, Optional

from deployment.runtime.models.research_request import ResearchRequest
from deployment.runtime.models.research_result import ResearchResult
from deployment.runtime.models.research_statistics import ResearchStatistics
from deployment.runtime.models.error_info import ErrorInfo
from deployment.runtime.event_bus import EventBus
from deployment.runtime.tool_executor import ToolExecutor
from deployment.workspace.workspace_manager import WorkspaceManager
from deployment.workspace.project_manager import ProjectManager
from khabrichacha.core.session import Session
from khabrichacha.llm.manager import LLMManager
from khabrichacha.core.orchestrator import Orchestrator
from khabrichacha.providers.provider_manager import ProviderManager
from khabrichacha.tools.registry import ToolRegistry
from khabrichacha.tools.builtin.search_web import SearchWebTool
from khabrichacha.tools.builtin.fetch_page import FetchPageTool
from deployment.reporting.report_exporter import ReportExporter
from deployment.workspace.workspace_schema import (
    RuntimeState, ResearchState as SchemaResearchState, PlannerState, ReferenceIndex, ReferenceEntry
)

from loguru import logger


class ResearchController:
    """Coordinates the entire lifecycle of a research request."""

    def __init__(self, workspace_manager: WorkspaceManager, provider_manager: ProviderManager, event_bus: Optional[EventBus] = None):
        self.workspace_manager = workspace_manager
        self.provider_manager = provider_manager
        self.event_bus = event_bus or EventBus()

    def start_research(self, request: ResearchRequest) -> ResearchResult:
        """
        Main entry point for UI or CLI to run research.
        Validates request, sets up project, executes research, generates reports.
        """
        start_time = time.time()
        result = ResearchResult(
            provider=request.provider,
            model=request.model
        )
        
        pm = ProjectManager(self.workspace_manager)
        
        try:
            self.event_bus.info("Controller", f"Starting research: {request.mission[:50]}...")
            
            # 1. Workspace and Project setup
            if request.resume and request.project_id:
                manifest = pm.resume_project(request.project_id)
            else:
                manifest = pm.create_project(
                    title=f"Research: {request.mission[:30]}",
                    mission=request.mission,
                    provider=request.provider,
                    model=request.model,
                    research_depth=request.depth
                )
                
            project_id = manifest.project_id
            result.project_id = project_id
            result.project_path = str(self.workspace_manager.projects / project_id)
            
            self.event_bus.info("Controller", f"Project {project_id} ready.")

            # 2. Session setup
            session = Session()
            session.config["llm"] = {
                "default_provider": request.provider,
                "temperature": 0.7,
                "max_tokens": 2048,
            }
            if "providers" not in session.config:
                session.config["providers"] = {}
            session.config["providers"][request.provider] = {
                "model": request.model,
            }
            session.config["research"] = {
                "depth": request.depth.lower(),
                "max_sources": request.metadata.get("max_sources", 5),
                "max_iterations": request.max_iterations,
            }

            # 3. LLMManager and Tool Executor & Middleware setup
            llm_manager = LLMManager(session.config)
            registry = ToolRegistry()
            executor = ToolExecutor(registry, project_id, result.project_path)
            
            # 4. Orchestration
            orchestrator = Orchestrator(
                session=session,
                llm_manager=llm_manager,
                tool_registry=executor
            )
            
            self.event_bus.info("Orchestrator", "Starting execution phase")
            try:
                orchestrator.run(request.mission)
            except Exception as orch_e:
                logger.error(f"Orchestration interrupted: {orch_e}")
                result.errors.append(ErrorInfo(component="Orchestrator", message=str(orch_e)))
                result.warnings.append("Research was interrupted but partial results may exist.")

            # 5. Extract Findings and Sources
            findings = session.research_state.get("findings", [])
            sources_list = []
            for t in session.state.tasks:
                if t.status == "completed" and t.result:
                    import json as _json
                    try:
                        parsed = _json.loads(t.result)
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, dict) and "url" in item:
                                    sources_list.append({"title": item.get("title", "Untitled"), "url": item["url"]})
                    except Exception:
                        pass

            # Generate insights using LLM
            evidence = ""
            try:
                if findings:
                    provider_obj = llm_manager.get_provider()
                    prompt = (
                        f"You are an expert research analyst. The user requested research on: '{request.mission}'.\n"
                        f"Based on the following raw findings extracted from various sources, please organize, synthesize, and present a well-structured summary. "
                        f"Arrange the information logically, provide clear insights, and eliminate redundancy.\n\n"
                        f"Raw Findings:\n" + "\n".join(findings)
                    )
                    evidence = provider_obj.generate(prompt)
            except Exception as e:
                logger.error(f"Failed to generate LLM insights: {e}")

            # Build timeline
            timeline_parts = []
            for i in range(1, session.research_state.get("iteration", 0) + 1):
                s = session.runtime.get(f"iteration_{i}_summary")
                if s:
                    timeline_parts.append(s)
            timeline = "\n\n".join(timeline_parts)

            # 6. Report Generation
            self.event_bus.info("Report", "Generating output reports")
            exporter = ReportExporter()
            exports = exporter.generate(
                title=manifest.title,
                mission=manifest.mission,
                provider=request.provider,
                model=request.model,
                findings=findings,
                sources=sources_list,
                evidence=evidence,
                research_state=session.research_state,
                timeline=timeline
            )
            
            # 7. Save Everything
            runtime_state = RuntimeState(
                session_id=session.session_id,
                variables={k: str(v)[:500] for k, v in session.runtime.items()},
            )
            research_st = SchemaResearchState(**session.research_state)
            planner_st = PlannerState(steps=session.state.variables.get("plan_steps", []))
            ref_entries = [ReferenceEntry(title=s.get("title", ""), url=s.get("url", "")) for s in sources_list]
            ref_index = ReferenceIndex(entries=ref_entries, total=len(ref_entries))

            result.success = len(result.errors) == 0
            pm.update_manifest(
                project_id,
                status="completed" if result.success else "failed",
                iterations=session.research_state.get("iteration", 0),
                source_count=len(sources_list),
                evidence_count=len(findings),
            )

            pm.save_project(
                project_id,
                runtime=runtime_state,
                research_state=research_st,
                planner_state=planner_st,
                references=ref_index,
                report_md=exports["report_md"],
                report_json=exports["report_json"],
                report_pdf_bytes=exports.get("report_pdf_bytes"),
            )
            pm.unlock_project(project_id)
            
            # 8. Populate final result paths
            if "md" in request.output_formats:
                result.report_md_path = os.path.join(result.project_path, "report.md")
            if "json" in request.output_formats:
                result.report_json_path = os.path.join(result.project_path, "report.json")
            if "pdf" in request.output_formats:
                result.report_pdf_path = os.path.join(result.project_path, "report.pdf")

            result.iterations = session.research_state.get("iteration", 0)
            result.evidence_count = len(findings)
            result.source_count = len(sources_list)
            
            # Basic stats mapping
            result.statistics.elapsed_time = time.time() - start_time
            result.statistics.iterations = result.iterations
            result.elapsed_time = result.statistics.elapsed_time
            
            self.event_bus.info("Controller", "Research completed.")
            
        except Exception as e:
            logger.error(f"ResearchController error: {e}", exc_info=True)
            result.success = False
            result.errors.append(ErrorInfo(
                component="Controller",
                message=str(e),
                details=repr(e)
            ))
            
            if result.project_id:
                try:
                    pm.update_manifest(result.project_id, status="failed")
                    pm.unlock_project(result.project_id)
                except:
                    pass

        return result
