"""
Agent-native skill system with cognitive capability abstraction.

Skills are agent-visible capabilities that LLMs can understand and select,
not just internal implementation details.
"""

from lib.skills.base import BaseSkill, SkillInput, SkillOutput
from lib.skills.registry import SkillRegistry
from lib.skills.factory import create_default_skill_registry
from lib.skills.general_search import GeneralSearchSkill, GeneralSearchInput, GeneralSearchOutput, DocumentResult
from lib.skills.doc_search import DocumentSearchSkill, DocumentSearchInput, DocumentSearchOutput
from lib.skills.neighbour_search import NeighbourSearchSkill, NeighbourSearchInput, NeighbourSearchOutput

__all__ = [
    "BaseSkill",
    "SkillInput",
    "SkillOutput",
    "SkillRegistry",
    "create_default_skill_registry",
    "GeneralSearchSkill",
    "GeneralSearchInput",
    "GeneralSearchOutput",
    "DocumentSearchSkill",
    "DocumentSearchInput",
    "DocumentSearchOutput",
    "NeighbourSearchSkill",
    "NeighbourSearchInput",
    "NeighbourSearchOutput",
    "DocumentResult",
]

