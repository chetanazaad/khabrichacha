import json
from typing import Optional, Dict, Any
from khabrichacha.core.session import Session
from khabrichacha.core.planner import Planner
from khabrichacha.core.state import Task
from khabrichacha.tools.registry import ToolRegistry
from khabrichacha.llm.manager import LLMManager
from loguru import logger

# Import all built-in tools
from khabrichacha.tools.builtin import register_builtin_tools
from khabrichacha.tools.builtin.search_web import SearchWebTool
from khabrichacha.tools.builtin.search_news import SearchNewsTool
from khabrichacha.tools.builtin.fetch_page import FetchPageTool
from khabrichacha.tools.builtin.fetch_pdf import FetchPDFTool
from khabrichacha.tools.builtin.python_executor import PythonExecutorTool
from khabrichacha.tools.builtin.report_generator import ReportGeneratorTool


class Orchestrator:
    def __init__(self, session: Session, llm_manager: LLMManager, tool_registry: ToolRegistry):
        self.session = session
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self.planner = Planner(llm_manager=self.llm_manager)
        self._register_all_tools()

    def _register_all_tools(self):
        """Register all builtin tools to the registry."""
        register_builtin_tools(self.tool_registry)
        
        new_tools = [
            SearchWebTool(),
            SearchNewsTool(),
            FetchPageTool(),
            FetchPDFTool(),
            PythonExecutorTool(),
            ReportGeneratorTool()
        ]
        
        for tool in new_tools:
            if not self.tool_registry.has_tool(tool.name):
                self.tool_registry.register_tool(tool)

    def run(self, goal: str) -> Dict[str, Any]:
        """
        Executes the entire planning and task execution cycle for a goal.
        """
        state = self.session.state
        if not state.tasks:
            logger.info(f"No active task list for goal. Generating plan...")
            available_tool_names = self.tool_registry.list_tools()
            plan = self.planner.generate_plan(goal, available_tool_names)
            
            # Map plan steps to tasks in the execution state
            state.tasks = [
                Task(id=step.id, description=step.description)
                for step in plan.steps
            ]
            state.variables["plan_steps"] = [step.model_dump() for step in plan.steps]
            state.status = "running"
            
        # Execute each pending task
        for task in state.tasks:
            if task.status == "pending":
                logger.info(f"Orchestrating task: {task.description} (ID: {task.id})")
                state.update_task_status(task.id, "running")
                
                # Fetch matching plan step for tool instructions
                tool_name = None
                args = {}
                plan_steps = state.variables.get("plan_steps", [])
                for step in plan_steps:
                    if step["id"] == task.id:
                        tool_name = step.get("tool_name")
                        args = step.get("args") or {}
                        break
                
                # Execute the assigned tool
                try:
                    raw_result = self.execute_tool(tool_name, args)
                    
                    # Convert dicts/lists to JSON string for Task.result type safety
                    if isinstance(raw_result, (dict, list)):
                        result_str = json.dumps(raw_result)
                    else:
                        result_str = str(raw_result)
                        
                    state.update_task_status(task.id, "completed", result=result_str)
                    self.session.add_tool_message(tool_name or "orchestrator", result_str)
                except Exception as e:
                    error_msg = f"Task failed during execution: {e}"
                    logger.error(error_msg)
                    state.update_task_status(task.id, "failed", result=error_msg)
                    # Continue execution instead of crashing
        
        # All tasks evaluated. Now aggregate findings and sources.
        findings = []
        sources = []
        
        for task in state.tasks:
            if task.status != "completed" or not task.result:
                continue
                
            res_str = task.result
            parsed_res = None
            
            # Attempt JSON parse
            if (res_str.startswith("{") and res_str.endswith("}")) or (res_str.startswith("[") and res_str.endswith("]")):
                try:
                    parsed_res = json.loads(res_str)
                except Exception:
                    pass
                    
            if parsed_res is not None:
                if isinstance(parsed_res, list):
                    for item in parsed_res:
                        if isinstance(item, dict):
                            title = item.get("title") or item.get("name") or "Untitled Source"
                            url = item.get("url") or item.get("link") or ""
                            snippet = item.get("snippet") or item.get("summary") or item.get("description") or ""
                            
                            if url:
                                sources.append({"title": title, "url": url})
                            if snippet:
                                findings.append(f"{title}: {snippet}")
                            elif title:
                                findings.append(f"Referenced: {title}")
                elif isinstance(parsed_res, dict):
                    if "url" in parsed_res and "content" in parsed_res:
                        url = parsed_res["url"]
                        title = parsed_res.get("title") or "Untitled Page"
                        content = parsed_res["content"]
                        if url:
                            sources.append({"title": title, "url": url})
                        if content:
                            findings.append(f"Content from {title}: {content[:300]}...")
                    elif "success" in parsed_res and ("stdout" in parsed_res or "stderr" in parsed_res):
                        stdout = parsed_res.get("stdout", "")
                        stderr = parsed_res.get("stderr", "")
                        if parsed_res.get("success"):
                            findings.append(f"Code Analysis Result: {stdout[:500]}")
                        else:
                            findings.append(f"Code Analysis Error: {stderr[:500]}")
            else:
                findings.append(str(res_str))
                
        # Deduplicate findings and sources
        unique_findings = list(dict.fromkeys(findings))
        unique_sources = []
        seen_urls = set()
        for s in sources:
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                unique_sources.append(s)
                
        if not unique_findings:
            unique_findings = ["No actionable findings were collected during the execution phase."]
            
        # Generate the final report
        report_args = {
            "title": f"Research Report: {goal}",
            "objective": goal,
            "findings": unique_findings,
            "sources": unique_sources
        }
        
        try:
            report_tool = self.tool_registry.get_tool("generate_report")
            report_result = report_tool.execute(report_args)
            report_markdown = report_result.get("markdown", "")
            success = True
        except Exception as e:
            logger.error(f"Failed to generate final report: {e}")
            report_markdown = f"# Research Report\n\nFailed to generate report: {e}"
            success = False
            
        state.variables["report"] = report_markdown
        self.session.add_assistant_message(report_markdown)
        state.status = "completed"
        logger.info("Goal orchestration successfully finished.")
        
        return {
            "success": success,
            "report": report_markdown,
            "session": self.session
        }

    def execute_tool(self, tool_name: Optional[str], args: dict) -> Any:
        if not tool_name:
            return "Task completed via direct reasoning."
            
        if self.tool_registry.has_tool(tool_name):
            return self.tool_registry.execute(tool_name, args)
        else:
            logger.warning(f"Tool '{tool_name}' not found in registry. Running in mock simulation.")
            return f"Mock output from unregistered tool '{tool_name}' with arguments: {args}"
