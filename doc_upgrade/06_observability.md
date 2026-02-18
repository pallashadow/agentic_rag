# Observability: LangSmith Integration

## Current State

Basic logging with `app_logger.py`

## Modern Addition

LangSmith for LLM observability

## Benefits

- Track LLM calls, tokens, costs
- Debug prompt issues
- Monitor performance
- A/B test prompts

## Implementation

```python
# lib/llm/litellm_api.py
import os
from litellm import acompletion

# Enable LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = "chatbot-milesguo"

# LiteLLM automatically sends traces to LangSmith when enabled
```

## Files to Modify

- `lib/llm/litellm_api.py` - Add LangSmith configuration
- `.env.example` - Add `LANGSMITH_API_KEY`

