from typing import Optional
from khabrichacha.core.session import Session
from khabrichacha.core.planner import Planner
from khabrichacha.core.state import Task
from khabrichacha.tools.registry import ToolRegistry
from khabrichacha.llm.manager import LLMManager
from loguru import logger

class Orchestrator:
    def __init__(self, session: Session, llm_manager: LLMManager, tool_registry: ToolRegistry):
        self.session = session
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self.planner = Planner(llm_manager=self.llm_manager)

    def run(self, goal: str):
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
                    result = self.execute_tool(tool_name, args)
                    state.update_task_status(task.id, "completed", result=result)
                    self.session.add_tool_message(tool_name or "orchestrator", result)
                except Exception as e:
                    error_msg = f"Task failed during execution: {e}"
                    logger.error(error_msg)
                    state.update_task_status(task.id, "failed", result=error_msg)
                    state.status = "failed"
                    return
                
        state.status = "completed"
        logger.info("Goal orchestration successfully finished.")

    def execute_tool(self, tool_name: Optional[str], args: dict) -> str:
        if not tool_name:
            return "Task completed via direct reasoning."
            
        if self.tool_registry.has_tool(tool_name):
            tool = self.tool_registry.get_tool(tool_name)
            logger.info(f"Executing tool '{tool_name}' with args {args}")
            try:
                return tool.execute(args)
            except Exception as e:
                raise RuntimeError(f"Error executing {tool_name}: {e}")
        else:
            logger.warning(f"Tool '{tool_name}' not found in registry. Running in mock simulation.")
            return f"Mock output from unregistered tool '{tool_name}' with arguments: {args}"
