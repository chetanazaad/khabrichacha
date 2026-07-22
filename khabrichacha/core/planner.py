import sys
import json
import re
from typing import List, Optional, Dict, Any, Tuple
from loguru import logger
from pydantic import BaseModel

class PlanStep(BaseModel):
    id: str
    description: str
    tool_name: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    depends_on: List[str] = []
    status: str = "pending"  # pending, running, completed, failed

class Plan(BaseModel):
    goal: str
    steps: List[PlanStep] = []

class AdaptivePlan(BaseModel):
    continue_research: bool
    reason: str
    steps: List[PlanStep] = []

class Planner:
    def __init__(self, llm_manager=None):
        self.llm_manager = llm_manager

    def _get_tool_registry(self):
        # Try to find the tool_registry from the caller's frame (orchestrator)
        try:
            frame = sys._getframe(1)
            while frame:
                if 'self' in frame.f_locals:
                    caller_self = frame.f_locals['self']
                    if hasattr(caller_self, 'tool_registry'):
                        return caller_self.tool_registry
                frame = frame.f_back
        except Exception:
            pass
            
        # Fallback to creating a new registry with built-ins if not found
        from khabrichacha.tools.registry import ToolRegistry
        from khabrichacha.tools.builtin import register_builtin_tools
        from khabrichacha.tools.builtin.search_web import SearchWebTool
        from khabrichacha.tools.builtin.search_news import SearchNewsTool
        from khabrichacha.tools.builtin.fetch_page import FetchPageTool
        from khabrichacha.tools.builtin.fetch_pdf import FetchPDFTool
        from khabrichacha.tools.builtin.python_executor import PythonExecutorTool
        from khabrichacha.tools.builtin.report_generator import ReportGeneratorTool
        
        registry = ToolRegistry()
        register_builtin_tools(registry)
        for tool in [SearchWebTool(), SearchNewsTool(), FetchPageTool(), 
                     FetchPDFTool(), PythonExecutorTool(), ReportGeneratorTool()]:
            if not registry.has_tool(tool.name):
                registry.register_tool(tool)
        return registry

    def generate_plan(self, goal: str, available_tools: Optional[List[str]] = None) -> Plan:
        logger.info("Planning Started")
        tools = available_tools or []

        if not self.llm_manager:
            logger.warning("LLMManager not provided. Falling back to default plan.")
            return self._build_fallback_plan(goal, tools)

        try:
            logger.info("LLM Planning")
            system_prompt, user_prompt = self._build_prompt(goal, tools)
            steps_data = self._call_llm_and_parse_with_retry(user_prompt, system_prompt)
            valid_steps = self._validate_steps(steps_data, tools)

            if not valid_steps:
                raise ValueError("Plan contains no execution steps.")

            plan = Plan(goal=goal, steps=valid_steps)
            logger.info(f"Generated Plan: {plan.model_dump_json(indent=2)}")
            logger.info("Validation Complete")
            return plan
            return plan
        except Exception as e:
            logger.error(f"Errors during LLM planning: {e}")
            return self._build_fallback_plan(goal, tools)

    def generate_adaptive_plan(
        self,
        goal: str,
        available_tools: List[str],
        current_findings: List[str],
        current_sources: List[Dict[str, str]],
        previous_summary: Optional[str],
        iteration: int,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info(f"Adaptive Planning Iteration {iteration}")
        
        if not self.llm_manager:
            logger.warning("LLMManager not provided. Falling back to deterministic adaptive planning.")
            return self._build_adaptive_fallback(goal, available_tools, current_sources, iteration, config)
            
        try:
            # Build prompt
            system_prompt = (
                "You are an Adaptive AI Research Planner (LLM-1 Router).\n"
                "Your top priority is to minimize latency and stop early if the answer is clear.\n"
                "Evaluate the current findings against the original goal:\n"
                "- If the current findings or sources ALREADY provide sufficient information to answer the goal, YOU MUST set 'continue_research': false and generate no steps.\n"
                "- Only set 'continue_research': true if crucial information is demonstrably missing.\n"
                "Do not repeat exact queries or fetch the same URLs already collected.\n"
                "\n"
                "IMPORTANT - stay anchored to the original goal:\n"
                "Every search query and step you generate must directly help answer the "
                "ORIGINAL GOAL below -- not just be loosely related to something mentioned in passing.\n"
                "\n"
                "Return ONLY valid JSON:\n"
                "{\n"
                '  "continue_research": false,\n'
                '  "reason": "Sufficient evidence collected to answer the question directly.",\n'
                '  "steps": []\n'
                "}\n\n"
            )
            
            registry = self._get_tool_registry()
            tools_info = []
            for name in available_tools:
                if registry.has_tool(name):
                    t = registry.get_tool(name)
                    tools_info.append(f"- {name}: {t.description}\n  Inputs: {t.inputs}")
            tools_str = "\n".join(tools_info) if tools_info else "No tools available."
            
            findings_str = "\n".join(f"- {f}" for f in current_findings[:20]) if current_findings else "None"
            sources_str = "\n".join(f"- {s.get('title', '')} ({s.get('url', '')})" for s in current_sources) if current_sources else "None"
            
            user_prompt = (
                f"Original Goal: {goal}\n\n"
                f"Iteration: {iteration}\n"
                f"Previous Iteration Summary:\n{previous_summary or 'None'}\n\n"
                f"Current Sources:\n{sources_str}\n\n"
                f"Current Findings (truncated):\n{findings_str}\n\n"
                f"Available Tools:\n{tools_str}\n\n"
                "Generate the JSON adaptive plan now."
            )
            
            data = self._call_llm_and_parse_with_retry(user_prompt, system_prompt)
            
            # Validate JSON
            if "continue_research" not in data or "reason" not in data:
                raise ValueError("JSON must contain 'continue_research' and 'reason'.")
                
            steps_data = {"steps": data.get("steps", [])}
            valid_steps = self._validate_steps(steps_data, available_tools)

            # Ensure Iteration 1 NEVER exits with 0 steps
            if iteration == 1 and not valid_steps:
                logger.warning("Planner generated 0 steps on Iteration 1. Injecting mandatory search step.")
                if "search_web" in available_tools:
                    valid_steps = [
                        PlanStep(
                            tool_name="search_web",
                            arguments={"query": goal, "max_results": 5},
                            thought="Mandatory initial web search step."
                        )
                    ]
                    data["continue_research"] = True
            
            plan = AdaptivePlan(
                continue_research=bool(data["continue_research"]) if not (iteration == 1 and valid_steps) else True,
                reason=str(data.get("reason", "Initial research step")),
                steps=valid_steps
            )
            
            logger.info(f"Generated Adaptive Plan: continue={plan.continue_research}, steps={len(plan.steps)}")
            return plan.model_dump()
            
        except Exception as e:
            logger.error(f"Errors during LLM adaptive planning: {e}")
            return self._build_adaptive_fallback(goal, available_tools, current_sources, iteration, config)
            
    def _build_adaptive_fallback(
        self, goal: str, available_tools: List[str], current_sources: List[Dict[str, str]], iteration: int, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        from urllib.parse import urlparse
        
        max_iter = config.get("max_iterations", 5)
        min_sources = config.get("min_sources", 8)
        min_unique = config.get("min_unique_sources", 5)
        
        total_sources = len(current_sources)
        unique_domains = len(set(urlparse(s.get("url", "")).netloc for s in current_sources if s.get("url")))
        
        continue_research = True
        reason = ""
        
        if iteration >= max_iter:
            continue_research = False
            reason = "Max iterations reached."
        elif total_sources >= min_sources and unique_domains >= min_unique:
            continue_research = False
            reason = "Sufficient sources and domains collected."
            
        steps = []
        if continue_research:
            goal_lower = goal.lower()
            gov_keywords = {"government", "budget", "policy", "gov"}
            acad_keywords = {"research", "study", "paper"}
            
            is_gov = any(kw in goal_lower for kw in gov_keywords)
            is_acad = any(kw in goal_lower for kw in acad_keywords)
            
            query_modifiers = {
                1: "",
                2: "news updates recent",
                3: "detailed analysis",
                4: "challenges future outlook",
                5: "case study summary"
            }
            modifier = query_modifiers.get(iteration, "developments")
            query = f"{goal} {modifier}".strip()
            
            if is_gov and "search_web" in available_tools:
                steps.append(PlanStep(id="1", description=f"Search government sites for {modifier}", tool_name="search_web", args={"query": f"{query} site:gov"}, depends_on=[]))
                if "fetch_page" in available_tools:
                    steps.append(PlanStep(id="2", description="Fetch results", tool_name="fetch_page", args={"url": "${step1[*].url}"}, depends_on=["1"]))
            elif is_acad and "search_web" in available_tools:
                steps.append(PlanStep(id="1", description=f"Search academic sites for {modifier}", tool_name="search_web", args={"query": f"{query} site:edu OR site:org"}, depends_on=[]))
                if "fetch_page" in available_tools:
                    steps.append(PlanStep(id="2", description="Fetch results", tool_name="fetch_page", args={"url": "${step1[*].url}"}, depends_on=["1"]))
            elif "search_news" in available_tools:
                steps.append(PlanStep(id="1", description=f"Search broader news for {modifier}", tool_name="search_news", args={"query": query}, depends_on=[]))
                if "fetch_page" in available_tools:
                    steps.append(PlanStep(id="2", description="Fetch results", tool_name="fetch_page", args={"url": "${step1[*].url}"}, depends_on=["1"]))
            else:
                continue_research = False
                reason = "Cannot generate fallback steps."
                steps = []
                
        plan = AdaptivePlan(continue_research=continue_research, reason=reason, steps=steps)
        return plan.model_dump()

    def _build_prompt(self, goal: str, available_tools: List[str]) -> Tuple[str, str]:
        logger.info("Prompt Generated")
        system_prompt = (
            "You are an AI Research Planner.\n"
            "Your only job is to produce the execution plan.\n"
            "Never execute tools. Never summarize. Never answer the user.\n"
            "Only decide the sequence of actions.\n"
            "Only use tools from the available_tools list.\n"
            "If a tool does not exist, do NOT invent it.\n"
            "Every task should be atomic.\n"
            "Every step must directly help answer the stated Research Goal -- do not "
            "introduce tangential topics or sub-entities that are not clearly necessary "
            "to answer it.\n"
            "You must return ONLY valid JSON. No markdown, no explanation.\n"
            "{\n"
            '  "steps": [\n'
            "    {\n"
            '      "id": "1",\n'
            '      "description": "...",\n'
            '      "tool_name": "...",\n'
            '      "args": {},\n'
            '      "depends_on": []\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
        )
        
        registry = self._get_tool_registry()
        tools_info = []
        for name in available_tools:
            if registry.has_tool(name):
                t = registry.get_tool(name)
                tools_info.append(f"- {name}: {t.description}\n  Inputs: {t.inputs}")
            else:
                tools_info.append(f"- {name}")
                
        tools_str = "\n".join(tools_info) if tools_info else "No tools available."
        
        user_prompt = (
            f"Research Goal: {goal}\n\n"
            f"Available Tools:\n{tools_str}\n\n"
            "Generate the JSON execution plan now."
        )
        return system_prompt, user_prompt

    def _call_llm_and_parse_with_retry(self, user_prompt: str, system_prompt: str, max_retries: int = 1) -> Dict[str, Any]:
        """
        Calls the LLM and parses its response as JSON, retrying once with a
        corrective follow-up prompt if parsing fails. Small/local models are
        considerably more prone than large hosted ones to wrapping JSON in
        explanatory text, adding a chatty preamble, or using code fences
        even when explicitly told not to -- a single corrective retry
        (showing the model its own parse error) meaningfully improves
        reliability for exactly this case without an unbounded retry loop
        that would multiply latency/cost.
        """
        last_error: Optional[Exception] = None
        current_user_prompt = user_prompt
        for attempt in range(max_retries + 1):
            response_text = self._call_llm(current_user_prompt, system_prompt)
            try:
                return self._parse_response(response_text)
            except Exception as e:
                last_error = e
                logger.warning(f"Plan JSON parse attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    current_user_prompt = (
                        f"{user_prompt}\n\n"
                        f"Your previous response could not be parsed as JSON: {e}\n"
                        f"Respond again with ONLY the raw JSON object. Do not use markdown "
                        f"code fences, do not add any explanation, and do not include any "
                        f"text before or after the JSON object."
                    )
        raise last_error

    def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        logger.info("Sending Prompt for Planning (LLM-1 Ingestion)")
        try:
            if hasattr(self.llm_manager, "get_ingestion_provider"):
                provider = self.llm_manager.get_ingestion_provider()
            else:
                provider = self.llm_manager.get_provider()
        except Exception as e:
            raise RuntimeError(f"Failed to get LLM provider for planning: {e}")
            
        response = provider.generate(prompt, system_prompt=system_prompt)
        logger.info("Received Response")
        return response


    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        logger.info("Parsing JSON")
        if not response_text:
            raise ValueError("Empty response received from LLM.")
            
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
            
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Small/local models frequently add a chatty preamble or
            # postamble around the JSON even without code fences (e.g.
            # "Here's the plan: {...} Let me know if you'd like changes.").
            # As a last resort before giving up, try to extract the
            # outermost {...} block by brace-matching and parse that
            # instead of the whole response.
            extracted = self._extract_json_object(cleaned)
            if extracted is not None:
                try:
                    return json.loads(extracted)
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Failed to parse JSON: {e}")

    @staticmethod
    def _extract_json_object(text: str) -> Optional[str]:
        """
        Finds the first balanced {...} block in `text` by brace-matching
        (not just the first '{' to the last '}', which would incorrectly
        span multiple separate objects or trailing chatter containing
        stray braces).
        """
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    def _validate_steps(self, data: Dict[str, Any], available_tools: List[str]) -> List[PlanStep]:
        if not isinstance(data, dict) or "steps" not in data:
            raise ValueError("Invalid JSON format: missing 'steps' array.")
            
        steps_list = data["steps"]
        if not isinstance(steps_list, list):
            raise ValueError("'steps' must be an array.")

        valid_steps = []
        seen_ids = set()
        tools_set = set(available_tools) if available_tools else set()

        for idx, step_data in enumerate(steps_list):
            if not isinstance(step_data, dict):
                raise ValueError(f"Step at index {idx} is not a valid object.")

            step_id = step_data.get("id")
            description = step_data.get("description")
            tool_name = step_data.get("tool_name")
            args = step_data.get("args")
            depends_on = step_data.get("depends_on", [])

            if not step_id or not isinstance(step_id, str):
                raise ValueError(f"Invalid or missing 'id' at step {idx}.")
            if step_id in seen_ids:
                raise ValueError(f"Duplicate step ID '{step_id}'.")
            if not description or not isinstance(description, str):
                raise ValueError(f"Invalid or missing 'description' at step {idx}.")
            if tool_name is not None:
                if not isinstance(tool_name, str):
                    raise ValueError(f"Invalid 'tool_name' type at step {idx}.")
                if tool_name not in tools_set:
                    raise ValueError(f"Invalid tool_name '{tool_name}' at step {idx}. Not in available_tools.")
            if args is not None and not isinstance(args, dict):
                raise ValueError(f"Invalid 'args' type at step {idx}.")
            if not isinstance(depends_on, list):
                raise ValueError(f"Invalid 'depends_on' type at step {idx}.")

            for dep in depends_on:
                if not isinstance(dep, str):
                    raise ValueError(f"Invalid dependency ID '{dep}' at step {idx}.")
                if dep not in seen_ids:
                    raise ValueError(f"Dependency '{dep}' for step '{step_id}' does not exist or precedes it.")

            seen_ids.add(step_id)
            valid_steps.append(PlanStep(
                id=step_id,
                description=description,
                tool_name=tool_name,
                args=args,
                depends_on=depends_on,
                status="pending"
            ))

        return valid_steps

    def _build_fallback_plan(self, goal: str, available_tools: List[str]) -> Plan:
        logger.info("Fallback Planning")
        
        goal_lower = goal.lower()
        
        # Check heuristics
        news_keywords = {"news", "today", "latest", "breaking", "headlines"}
        is_news = any(kw in goal_lower for kw in news_keywords)
        
        pdf_keywords = {"pdf", "report", "whitepaper", "government report", "annual report", "budget"}
        is_pdf = any(kw in goal_lower for kw in pdf_keywords)
        
        python_keywords = {"calculate", "compare", "chart", "statistics", "growth", "percentage", "forecast", "analysis", "cagr", "rate"}
        is_python = any(kw in goal_lower for kw in python_keywords)
        
        urls_in_goal = re.findall(r'(https?://\S+)', goal)
        
        steps = []
        step_id = 1
        
        # 1. Search Step
        has_searched = False
        if is_news and "search_news" in available_tools:
            steps.append(PlanStep(
                id=str(step_id),
                description="Search for latest news",
                tool_name="search_news",
                args={"query": goal},
                depends_on=[]
            ))
            step_id += 1
            has_searched = True
        elif "search_web" in available_tools:
            steps.append(PlanStep(
                id=str(step_id),
                description="Search the web for information",
                tool_name="search_web",
                args={"query": goal},
                depends_on=[]
            ))
            step_id += 1
            has_searched = True
            
        # 2. Fetch Step
        if urls_in_goal:
            for url in urls_in_goal:
                if "fetch_page" in available_tools:
                    deps = [str(step_id - 1)] if step_id > 1 else []
                    steps.append(PlanStep(
                        id=str(step_id),
                        description=f"Fetch provided URL: {url}",
                        tool_name="fetch_page",
                        args={"url": url},
                        depends_on=deps
                    ))
                    step_id += 1
        else:
            if is_pdf and "fetch_pdf" in available_tools:
                deps = [str(step_id - 1)] if step_id > 1 else []
                # Reference the preceding search step's results instead of a
                # hardcoded placeholder URL, so this fallback plan (used
                # whenever no LLM is available to plan properly) actually
                # fetches something relevant instead of an unrelated dummy
                # PDF every single time.
                pdf_url = f"${{step{step_id - 1}[*].url}}" if has_searched else ""
                steps.append(PlanStep(
                    id=str(step_id),
                    description="Fetch the PDF document found via search",
                    tool_name="fetch_pdf",
                    args={"url": pdf_url},
                    depends_on=deps
                ))
                step_id += 1
            elif has_searched and "fetch_page" in available_tools:
                deps = [str(step_id - 1)] if step_id > 1 else []
                steps.append(PlanStep(
                    id=str(step_id),
                    description="Fetch content from search results",
                    tool_name="fetch_page",
                    args={"url": f"${{step{step_id - 1}[*].url}}"},
                    depends_on=deps
                ))
                step_id += 1
                
        # 3. Python Execution Step
        if is_python and "python_executor" in available_tools:
            deps = [str(step_id - 1)] if step_id > 1 else []
            steps.append(PlanStep(
                id=str(step_id),
                description="Perform data analysis and calculations",
                tool_name="python_executor",
                args={"code": f"# Analysis for {goal}\nprint('Performing calculations...')"},
                depends_on=deps
            ))
            step_id += 1
            
        # 4. Report Generation Step
        if "generate_report" in available_tools:
            deps = [str(step_id - 1)] if step_id > 1 else []
            steps.append(PlanStep(
                id=str(step_id),
                description="Generate final research report",
                tool_name="generate_report",
                args={
                    "title": f"Research Report: {goal}",
                    "objective": goal,
                    "findings": [],
                    "sources": []
                },
                depends_on=deps
            ))
            step_id += 1
            
        plan = Plan(goal=goal, steps=steps)
        logger.info(f"Generated Plan: {plan.model_dump_json(indent=2)}")
        logger.info("Validation Complete")
        return plan
