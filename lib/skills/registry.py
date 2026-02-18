"""
Registry for agent-native skills with tool export capabilities.
"""
from typing import Dict, List
from lib.skills.base import BaseSkill


class SkillRegistry:
    """Registry for agent-native skills with tool export capabilities."""
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
    
    def register(self, skill: BaseSkill):
        """Register a skill."""
        self._skills[skill.name] = skill
    
    def get(self, name: str) -> BaseSkill:
        """Get a skill by name."""
        if name not in self._skills:
            raise ValueError(f"Skill '{name}' not found. Available: {self.list_available()}")
        return self._skills[name]
    
    def list_available(self) -> List[str]:
        """List all available skill names."""
        return list(self._skills.keys())
    
    def get_all_tool_schemas(self) -> List[dict]:
        """Get all skills as OpenAI tool schemas for LLM function calling."""
        return [skill.to_tool_schema() for skill in self._skills.values()]
    
    def get_all_mcp_tools(self) -> List[dict]:
        """Get all skills as MCP tool specifications."""
        return [skill.to_mcp_tool_spec() for skill in self._skills.values()]
    
    def get_skill_descriptions(self) -> Dict[str, str]:
        """Get skill names and descriptions for LLM planning."""
        return {
            name: skill.description
            for name, skill in self._skills.items()
        }

