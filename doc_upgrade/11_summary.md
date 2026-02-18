# Summary

## What to Replace

- **langchain-text-splitters**: Can be replaced with `tiktoken`-based chunking, but current usage is minimal and acceptable

## What to Add

1. **Function Calling**: Replace JSON Schema structured outputs with native tool calling
2. **MCP Integration**: Standardize external tool interfaces
3. **Skill System**: Make search operations extensible
4. **LangSmith**: Add observability for LLM calls
5. **Pydantic Models**: Better type safety for structured outputs

## What to Keep

- ✅ **LangGraph**: Excellent choice, keep it
- ✅ **LiteLLM**: Good abstraction, keep it
- ✅ **YAML Prompts**: Works well, no need to change
- ✅ **Custom Elasticsearch Integration**: Well-designed, keep it

## Overview

The project is already quite modern with LangGraph. The main improvements are:

1. Using function calling instead of JSON Schema
2. Adding a skill/plugin system for extensibility
3. Adding MCP for standardized tool interfaces
4. Adding observability with LangSmith

