from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from loguru import logger
import json

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

class Planner:
    def __init__(self, llm_manager=None):
        self.llm_manager = llm_manager

    def generate_plan(self, goal: str, available_tools: Optional[List[str]] = None) -> Plan:
        logger.info("Planning Started")
        tools = available_tools or []

        if not self.llm_manager:
            logger.warning("LLMManager not provided. Falling back to default plan.")
            return self._build_fallback_plan(goal, tools)

        try:
            system_prompt, user_prompt = self._build_prompt(goal, tools)
            response_text = self._call_llm(user_prompt, system_prompt)
            steps_data = self._parse_response(response_text)
            valid_steps = self._validate_steps(steps_data, tools)

            if not valid_steps:
                raise ValueError("Plan contains no execution steps.")

            logger.info("Plan Generated")
            return Plan(goal=goal, steps=valid_steps)
        except Exception as e:
            logger.error(f"Errors: {e}")
            return self._build_fallback_plan(goal, tools)

    def _build_prompt(self, goal: str, available_tools: List[str]) -> Tuple[str, str]:
        logger.info("Prompt Generated")
        system_prompt = (
            "You are an AI Research Planner.\n"
            "Your only job is to produce the execution plan.\n"
            "Never execute tools.\n"
            "Never summarize.\n"
            "Never answer the user.\n"
            "Only decide the sequence of actions.\n"
            "Only use tools from the available_tools list.\n"
            "If a tool does not exist, do NOT invent it.\n"
            "Every task should be atomic.\n"
            "Bad task:\n"
            "Research everything about NVIDIA.\n"
            "Good tasks:\n"
            "Search latest NVIDIA news.\n"
            "Read earnings report.\n"
            "Compare analyst opinions.\n"
            "Generate final report.\n\n"
            "You must return ONLY valid JSON. No markdown, no explanation.\n"
            "{\n"
            '  "steps": [\n'
            "    {\n"
            '      "id": "step_1",\n'
            '      "description": "Search latest news",\n'
            '      "tool_name": "search_news",\n'
            '      "args": {\n'
            '          "query": "..."\n'
            "      },\n"
            '      "depends_on": []\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )
        
        tools_str = ", ".join(f"'{t}'" for t in available_tools) if available_tools else "No tools available."
        user_prompt = (
            f"Research Goal: {goal}\n"
            f"Available Tools: [{tools_str}]\n\n"
            "Generate the JSON execution plan now."
        )
        return system_prompt, user_prompt

    def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        logger.info("Sending Prompt")
        try:
            provider = self.llm_manager.get_provider()
        except Exception as e:
            raise RuntimeError(f"Failed to get LLM provider: {e}")
            
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
            raise ValueError(f"Failed to parse JSON: {e}")

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
        logger.info("Fallback Used")
        tool_1 = "workspace_init" if "workspace_init" in available_tools else None
        tool_2 = "execute_task" if "execute_task" in available_tools else None
        tool_3 = "execute_task" if "execute_task" in available_tools else None
        tool_4 = "summarize_results" if "summarize_results" in available_tools else None

        steps = [
            PlanStep(
                id="1.",
                description="Understand Goal",
                tool_name=tool_1,
                args={"goal": goal} if tool_1 else None,
                depends_on=[]
            ),
            PlanStep(
                id="2.",
                description="Search Information",
                tool_name=tool_2,
                args={"query": goal} if tool_2 else None,
                depends_on=["1."]
            ),
            PlanStep(
                id="3.",
                description="Analyze Information",
                tool_name=tool_3,
                args={"query": goal} if tool_3 else None,
                depends_on=["2."]
            ),
            PlanStep(
                id="4.",
                description="Generate Report",
                tool_name=tool_4,
                args={"goal": goal} if tool_4 else None,
                depends_on=["3."]
            )
        ]
        return Plan(goal=goal, steps=steps)
