"""
Factory helpers for composing a default skill registry.

Search wiring is encapsulated in the skills layer so agent nodes do not need to
know about SearchService/ElasticMix internals.
"""

from lib.search.elastic_mix import ElasticMix
from lib.search.search_service import SearchService
from lib.skills.registry import SkillRegistry
from lib.skills.general_search import GeneralSearchSkill
from lib.skills.doc_search import DocumentSearchSkill
from lib.skills.neighbour_search import NeighbourSearchSkill


def create_default_skill_registry() -> SkillRegistry:
    """Create a search-service-backed default skill registry for agent execution."""
    elastic_mix = ElasticMix()
    search_service = SearchService(elastic_mix)

    registry = SkillRegistry()
    registry.register(GeneralSearchSkill(search_service))
    registry.register(DocumentSearchSkill(search_service))
    registry.register(NeighbourSearchSkill(search_service))
    return registry


