import json
import re
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
    def __init__(self, session: Session, llm_manager: LLMManager, tool_registry: ToolRegistry, **kwargs):
        self.session = session
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self.planner = Planner(llm_manager=self.llm_manager)
        self._register_all_tools()
        
        self.cancel_event = kwargs.get("cancel_event")
        from deployment.runtime.event_bus import EventBus
        self.event_bus = EventBus()

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

    def resolve_path(self, data: Any, path_parts: list) -> Any:
        """Resolve a dot-notation/bracket-notation path against a data dictionary."""
        current = data
        for part in path_parts:
            if current is None:
                return None
            if part == '*':
                if isinstance(current, list):
                    return current
                elif isinstance(current, dict):
                    return list(current.values())
                return current
            
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def resolve_variables(self, val: Any) -> Any:
        """Recursively resolve ${stepX...} templates in strings, dicts, or lists."""
        if isinstance(val, dict):
            return {k: self.resolve_variables(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self.resolve_variables(v) for v in val]
        elif isinstance(val, str):
            exact_match = re.fullmatch(r'\$\{([^}]+)\}', val)
            if exact_match:
                path_str = exact_match.group(1)
                parts = [p for p in re.split(r'\.|\[|\]', path_str) if p]
                if not parts:
                    return val
                step_id = parts[0]
                rest = parts[1:]
                step_id = parts[0]
                rest = parts[1:]
                
                step_data = self._get_step_data_from_runtime(step_id)
                if step_data is not None:
                    if '*' in rest:
                        star_idx = rest.index('*')
                        base_parts = rest[:star_idx]
                        tail_parts = rest[star_idx+1:]
                        
                        base_data = self.resolve_path(step_data, base_parts)
                        if isinstance(base_data, list):
                            if not tail_parts:
                                return base_data
                            else:
                                return [self.resolve_path(item, tail_parts) for item in base_data if item is not None]
                    else:
                        resolved = self.resolve_path(step_data, rest)
                        if resolved is not None:
                            return resolved
                            
            def replace_match(m):
                path_str = m.group(1)
                parts = [p for p in re.split(r'\.|\[|\]', path_str) if p]
                if not parts:
                    return m.group(0)
                step_id = parts[0]
                rest = parts[1:]
                step_data = self._get_step_data_from_runtime(step_id)
                if step_data is not None:
                    resolved = self.resolve_path(step_data, rest)
                    if resolved is not None:
                        return str(resolved)
                return m.group(0)
                
            return re.sub(r'\$\{([^}]+)\}', replace_match, val)
        return val

    def _get_step_data_from_runtime(self, step_id: str) -> Any:
        # Check direct lookup first
        if step_id in self.session.runtime:
            return self.session.runtime[step_id]
            
        # Normalize step_id by stripping "step" prefix
        norm_id = step_id
        if step_id.lower().startswith("step"):
            norm_id = step_id[4:]
            
        current_iter = self.session.research_state.get("iteration", 1)
        
        # Try current iteration first
        candidate_keys = [
            f"iter{current_iter}_{norm_id}",
            f"iter{current_iter}_{step_id}"
        ]
        for key in candidate_keys:
            if key in self.session.runtime:
                return self.session.runtime[key]
                
        # Try searching other iterations in reverse order (most recent first)
        for it in range(current_iter - 1, 0, -1):
            candidate_keys = [
                f"iter{it}_{norm_id}",
                f"iter{it}_{step_id}"
            ]
            for key in candidate_keys:
                if key in self.session.runtime:
                    return self.session.runtime[key]
                    
        # General suffix search as fallback
        suffix1 = f"_{norm_id}"
        suffix2 = f"_{step_id}"
        matching_keys = []
        for k in self.session.runtime.keys():
            if k.endswith(suffix1) or k.endswith(suffix2):
                matching_keys.append(k)
        if matching_keys:
            # Sort to get the highest iteration prefix
            matching_keys.sort(reverse=True)
            return self.session.runtime[matching_keys[0]]
            
        return None

    def _generate_iteration_summary(self, goal: str, iteration: int, new_findings: list, sources_count: int, unique_domains_count: int) -> str:
        if not self.llm_manager:
            return (f"**Iteration {iteration} completed**\n"
                    f"- Collected {sources_count} total sources from {unique_domains_count} unique domains.\n"
                    f"- Findings extracted this cycle: {len(new_findings)}")
            
        try:
            provider = self.llm_manager.get_provider()
            prompt = (
                f"You are a research analyst. Given the goal: {goal}, and the newly collected findings from iteration {iteration}:\n"
                f"{chr(10).join(new_findings[:20])}\n\n"
                "Generate a very brief iteration summary in this exact format (do not use markdown blocks):\n"
                f"**Iteration {iteration}**\n"
                f"- Collected {sources_count} sources\n"
                f"- {unique_domains_count} unique domains\n"
                "- Main topics: <comma separated list>\n"
                "- Outstanding questions: <comma separated list>"
            )
            summary = provider.generate(prompt)
            return summary.strip()
        except Exception as e:
            logger.error(f"Failed to generate iteration summary via LLM: {e}")
            return f"**Iteration {iteration} completed**\nSources: {sources_count}."

    def run(self, goal: str) -> Dict[str, Any]:
        """
        Executes the entire planning and task execution cycle for a goal.
        """
        import time
        from urllib.parse import urlparse
        
        state = self.session.state
        research_config = self.session.config.get("research", {})
        
        max_iterations = research_config.get("max_iterations", 5)
        depth = research_config.get("depth", "standard")
        max_runtime_minutes = research_config.get("max_runtime_minutes", 15)
        
        # Backward compatibility / Quick mode
        if str(depth).lower() == "quick":
            max_iterations = 1
            
        # Validate LLM provider availability
        if (max_iterations > 1 or depth != "quick") and self.llm_manager:
            try:
                self.llm_manager.get_provider()
            except Exception as e:
                logger.error(f"LLM configuration error: {e}")
                return {
                    "success": False,
                    "report": f"# Research Execution Failed\n\n**LLM Provider Error**: {e}\n\nPlease verify that your API key is correctly configured.",
                    "session": self.session
                }
                
        available_tool_names = self.tool_registry.list_tools()
        start_time = time.time()
        
        all_findings = []
        all_sources = []
        seen_urls = set()
        
        state.status = "running"
        iteration = 1
        
        from deployment.runtime.event_bus import ResearchEvent
        while iteration <= max_iterations:
            if self.cancel_event and self.cancel_event.is_set():
                logger.info("Cancellation event set. Stopping Orchestrator run.")
                state.status = "failed"
                break
                
            elapsed_minutes = (time.time() - start_time) / 60
            if elapsed_minutes > max_runtime_minutes:
                logger.warning(f"Maximum runtime exceeded ({elapsed_minutes:.1f}m). Stopping research.")
                break
                
            logger.info(f"--- Starting Iteration {iteration} ---")
            self.event_bus.publish(ResearchEvent(
                level="INFO",
                component="Orchestrator",
                message=f"Starting Iteration {iteration}/{max_iterations}...",
                metadata={"progress": min(0.95, 0.15 + 0.75 * (iteration - 1) / max_iterations)}
            ))
            
            # 1. Planning phase
            if iteration == 1 and max_iterations == 1:
                logger.info("Executing single-pass fallback planning.")
                plan = self.planner.generate_plan(goal, available_tool_names)
                plan_steps = plan.steps
                continue_research = False # Stop after this
            else:
                prev_summary = self.session.runtime.get(f"iteration_{iteration-1}_summary") if iteration > 1 else None
                plan_dict = self.planner.generate_adaptive_plan(
                    goal=goal,
                    available_tools=available_tool_names,
                    current_findings=all_findings,
                    current_sources=all_sources,
                    previous_summary=prev_summary,
                    iteration=iteration,
                    config=research_config
                )
                continue_research = plan_dict.get("continue_research", False)
                if not continue_research and iteration > 1:
                    logger.info(f"Planner explicitly decided to stop: {plan_dict.get('reason')}")
                    break
                    
                # Setup steps and prefix IDs
                from khabrichacha.core.planner import PlanStep
                plan_steps = [PlanStep(**s) for s in plan_dict.get("steps", [])]
                for s in plan_steps:
                    s.id = f"iter{iteration}_{s.id}"
                    s.depends_on = [f"iter{iteration}_{d}" for d in s.depends_on]
                    
            if not plan_steps and continue_research:
                logger.info("Planner chose to continue but provided no steps.")
                break
                
            # 2. Append new tasks
            new_tasks = [Task(id=step.id, description=step.description) for step in plan_steps]
            state.tasks.extend(new_tasks)
            state.variables.setdefault("plan_steps", []).extend([step.model_dump() for step in plan_steps])
            
            # 3. Execute pending tasks
            for task in state.tasks:
                if self.cancel_event and self.cancel_event.is_set():
                    logger.info("Cancellation event set. Stopping Orchestrator task execution.")
                    state.status = "failed"
                    break
                if task.status == "pending":
                    logger.info(f"Orchestrating task: {task.description} (ID: {task.id})")
                    self.event_bus.publish(ResearchEvent(
                        level="INFO",
                        component="Orchestrator",
                        message=f"Executing step: {task.description}...",
                        metadata={"progress": min(0.95, 0.15 + 0.75 * (iteration - 1) / max_iterations + 0.05)}
                    ))
                    state.update_task_status(task.id, "running")
                    
                    tool_name = None
                    args = {}
                    for step in state.variables.get("plan_steps", []):
                        if step["id"] == task.id:
                            tool_name = step.get("tool_name")
                            args = step.get("args") or {}
                            break
                            
                    try:
                        resolved_args = self.resolve_variables(args)
                        raw_result = self.execute_tool(tool_name, resolved_args)
                        self.session.runtime[task.id] = raw_result
                        
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
                        
            # 4. Evaluate execution and extract new findings
            new_findings = []
            new_sources = []
            
            for task in state.tasks:
                if task.status != "completed" or not task.result:
                    continue
                # only process tasks from this iteration
                if task.id.startswith(f"iter{iteration}_") or max_iterations == 1:
                    parsed_res = None
                    res_str = task.result
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
                                    
                                    if url and url not in seen_urls:
                                        seen_urls.add(url)
                                        new_sources.append({"title": title, "url": url})
                                        all_sources.append({"title": title, "url": url})
                                    if snippet:
                                        new_findings.append(f"{title}: {snippet}")
                                        all_findings.append(f"{title}: {snippet}")
                        elif isinstance(parsed_res, dict):
                            if "url" in parsed_res and "content" in parsed_res:
                                url = parsed_res["url"]
                                title = parsed_res.get("title") or "Untitled Page"
                                content = parsed_res["content"]
                                if url and url not in seen_urls:
                                    seen_urls.add(url)
                                    new_sources.append({"title": title, "url": url})
                                    all_sources.append({"title": title, "url": url})
                                if content:
                                    new_findings.append(f"Content from {title}: {content[:300]}...")
                                    all_findings.append(f"Content from {title}: {content[:300]}...")
                            elif "success" in parsed_res:
                                stdout = parsed_res.get("stdout", "")
                                if parsed_res.get("success"):
                                    new_findings.append(f"Code Analysis Result: {stdout[:500]}")
                                    all_findings.append(f"Code Analysis Result: {stdout[:500]}")
                    else:
                        new_findings.append(str(res_str))
                        all_findings.append(str(res_str))
                        
            # 5. Generate iteration summary
            unique_domains = len(set(urlparse(s["url"]).netloc for s in all_sources if s.get("url")))
            summary = self._generate_iteration_summary(goal, iteration, new_findings, len(all_sources), unique_domains)
            self.session.runtime[f"iteration_{iteration}_summary"] = summary
            
            # Update research state
            self.session.research_state.update({
                "iteration": iteration,
                "completed": not continue_research,
                "total_sources": len(all_sources),
                "unique_domains": unique_domains,
                "findings": all_findings,
                "coverage": f"{(iteration/max_iterations)*100:.0f}%" if max_iterations > 1 else "100%"
            })
            
            if not continue_research:
                break
                
            iteration += 1

        # Final Report Generation
        evidence_list = []
        for task_id, output in self.session.runtime.items():
            if isinstance(output, dict) and "content" in output:
                evidence_list.append(output["content"])
            elif isinstance(output, list):
                for item in output:
                    if isinstance(item, dict) and "content" in item:
                        evidence_list.append(item["content"])
                        
        if not all_findings:
            all_findings = ["No actionable findings were collected."]
            
        report_args = {
            "title": f"Research Report: {goal}",
            "objective": goal,
            "findings": list(dict.fromkeys(all_findings)),
            "sources": all_sources
        }
        
        if evidence_list:
            report_args["evidence"] = "\n\n---\n\n".join(evidence_list)
            
        # Inject timeline into evidence block
        timeline_str = "## Research Timeline\n\n"
        for i in range(1, iteration + 1):
            summ = self.session.runtime.get(f"iteration_{i}_summary")
            if summ:
                timeline_str += f"{summ}\n\n"
                
        if timeline_str.strip() != "## Research Timeline":
            if "evidence" in report_args:
                report_args["evidence"] = timeline_str + "\n\n" + report_args["evidence"]
            else:
                report_args["evidence"] = timeline_str
        
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
