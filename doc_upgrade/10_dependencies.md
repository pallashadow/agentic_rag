# Dependencies to Add

```toml
# pyproject.toml additions

[tool.poetry.dependencies]
# For function calling
pydantic = "^2.0.0"  # Already used, ensure v2

# For MCP
mcp = "^0.1.0"  # When available, or use protocol directly

# For observability
langsmith = "^0.1.0"  # Optional, for LangSmith integration

# For better chunking (optional replacement)
tiktoken = "^0.5.0"  # If replacing langchain-text-splitters
```

