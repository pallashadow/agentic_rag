# Project Upgrade Guide: Modernization & LangChain Alternatives

This document identifies areas where LangChain can be replaced and suggests modern components to enhance the project architecture.

## Document Structure

This guide is organized into the following sections:

1. Done **[Current LangChain Usage](01_langchain_usage.md)** - Analysis of existing LangChain dependencies
2. Done **[Function Calling / Tools](02_function_calling.md)** - Replace JSON Schema with native tool calling
3. Done **[MCP Integration](03_mcp_integration.md)** - Model Context Protocol for standardized tool interfaces
4. **[Skill System](04_skill_system.md)** - Agent-native cognitive capability layer
5. **[Prompt Templates](05_prompt_templates.md)** - LangChain prompt templates (optional)
6. **[Observability](06_observability.md)** - LangSmith integration for LLM observability
7. **[Agent Framework](07_agent_framework.md)** - LangGraph modernization considerations
8. **[Structured Output](08_structured_output.md)** - Pydantic models for structured outputs
9. **[Migration Priority](09_migration_priority.md)** - Phased implementation plan
10. **[Dependencies](10_dependencies.md)** - Required and optional dependencies
11. **[Summary](11_summary.md)** - Overview of recommendations

## Quick Start

If you're looking for a specific topic, use the links above. For a high-level overview, see the [Summary](11_summary.md).

## Overview

The project is already quite modern with LangGraph. The main improvements are:

1. Using function calling instead of JSON Schema
2. Adding a skill/plugin system for extensibility
3. Adding MCP for standardized tool interfaces
4. Adding observability with LangSmith

