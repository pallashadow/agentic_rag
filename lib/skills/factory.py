"""
Factory helpers for composing a default skill registry.

MCP wiring is intentionally encapsulated in the skills layer so agent nodes
do not need to know about MCP/SearchService/ElasticMix internals.
"""

from lib.search.elastic_mix import ElasticMix
from lib.mcp import SearchService, SearchMCPServer
from lib.skills.registry import SkillRegistry
from lib.skills.general_search import GeneralSearchSkill
from lib.skills.doc_search import DocumentSearchSkill
from lib.skills.neighbour_search import NeighbourSearchSkill


def create_default_skill_registry() -> SkillRegistry:
    """Create a MCP-backed default skill registry for agent execution."""
    elastic_mix = ElasticMix()
    search_service = SearchService(elastic_mix)
    mcp_server = SearchMCPServer(search_service)

    registry = SkillRegistry()
    registry.register(GeneralSearchSkill(mcp_server))
    registry.register(DocumentSearchSkill(mcp_server))
    registry.register(NeighbourSearchSkill(mcp_server))
    return registry


