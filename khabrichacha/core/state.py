from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class Message(BaseModel):
    role: str  # user, assistant, system, tool
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    name: Optional[str] = None  # tool name or caller name

class Task(BaseModel):
    id: str
    description: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class State(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    messages: List[Message] = Field(default_factory=list)
    tasks: List[Task] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    status: str = "idle"
    current_step_index: int = 0

    def add_message(self, role: str, content: str, name: Optional[str] = None):
        self.messages.append(Message(role=role, content=content, name=name))
        self.updated_at = datetime.now()

    def update_task_status(self, task_id: str, status: str, result: Optional[str] = None):
        for task in self.tasks:
            if task.id == task_id:
                task.status = status
                if status == "running" and not task.started_at:
                    task.started_at = datetime.now()
                elif status in ["completed", "failed"]:
                    task.completed_at = datetime.now()
                    task.result = result
                break
        self.updated_at = datetime.now()
