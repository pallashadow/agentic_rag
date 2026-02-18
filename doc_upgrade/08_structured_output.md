# Structured Output Modernization

## Current

Manual JSON Schema with parsing

## Modern Alternative

Pydantic models with structured outputs

## Benefits

- Type safety
- Better validation
- IDE autocomplete
- Less error-prone parsing

## Implementation

```python
# lib/agentic/schemas.py
from pydantic import BaseModel, Field
from typing import Literal

class EntryResponse(BaseModel):
    query_type: Literal["greeting", "insult", "unclear", "need_rag"]
    expanded_queries: list[str] = Field(min_length=1, max_length=3)
    answer: str

# lib/llm/litellm_api.py
async def call_llm_structured(
    prompt: str,
    response_model: type[BaseModel],
    model_name: str = "gpt"
) -> BaseModel:
    """Call LLM with Pydantic structured output."""
    response = await acompletion(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": response_model.model_json_schema()
        }
    )
    return response_model.model_validate_json(response.choices[0].message.content)
```

