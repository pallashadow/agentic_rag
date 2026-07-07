"""
Base classes for agent-native skills with tool semantics.

Skills are cognitive capabilities that LLMs can understand and select,
not just internal implementation details.
"""
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Type, Any
import json
from lib.agentic.config import AgentState


class SkillInput(BaseModel):
    """Base class for skill input schemas."""
    pass


class SkillOutput(BaseModel):
    """Base class for skill output schemas."""
    pass


class BaseSkill(ABC):
    """Base class for agent-native skills with tool semantics."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM understanding."""
        ...
    
    @property
    @abstractmethod
    def input_model(self) -> Type[SkillInput]:
        """Pydantic model defining input schema."""
        ...
    
    @property
    @abstractmethod
    def output_model(self) -> Type[SkillOutput]:
        """Pydantic model defining output schema."""
        ...
    
    def to_tool_schema(self) -> dict:
        """Export skill as OpenAI-compatible tool schema for LLM calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema()
            }
        }
    
    @abstractmethod
    async def execute(self, input_data: SkillInput, state: AgentState | None = None) -> SkillOutput:
        """Execute the skill with validated input."""
        ...

