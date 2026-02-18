# Function Calling / Tools Instead of Structured Outputs

## Current Approach

The project uses JSON Schema structured outputs to get LLM decisions:
- Entry classification (`entry_llm_node.py`)
- Query expansion (`query_expand.py`)
- Answer validation (`reply_validation_node.py`)

## Modern Alternative

Use LiteLLM function calling / tool use

## Benefits

- Native support via LiteLLM's unified interface (works with GPT-4, Claude, Gemini)
- More reliable than JSON Schema parsing (automatic function call handling)
- Better error handling (LiteLLM handles model-specific differences)
- Native tool descriptions help LLM understand capabilities
- Consistent API across different LLM providers

## Implementation Example with LiteLLM

```python
# lib/llm/litellm_api.py - Add function calling support
async def call_llm_with_tools(
    prompt: str,
    tools: list[dict],
    model_name: str = "gpt",
    tool_choice: str = "auto"
) -> dict:
    """
    Call LLM with function calling support via LiteLLM.
    
    Args:
        prompt: User prompt
        tools: List of tool definitions in OpenAI format
        model_name: Model identifier for LiteLLM router
        tool_choice: "auto", "required", or "none"
    
    Returns:
        dict: Contains 'content' and 'tool_calls' (if any)
    """
    router = get_litellm_fallback_router()
    
    messages = [{"role": "user", "content": prompt}]
    
    # LiteLLM automatically handles tools parameter
    response = await router.acompletion(
        model=model_name,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=0.0
    )
    
    message = response.choices[0].message
    
    # Extract function calls if present
    result = {
        "content": message.content or "",
        "tool_calls": []
    }
    
    if hasattr(message, "tool_calls") and message.tool_calls:
        for tool_call in message.tool_calls:
            result["tool_calls"].append({
                "id": tool_call.id,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments
                }
            })
    
    return result

# lib/agentic/nodes/entry_llm_node.py (modernized with LiteLLM)
async def entry_llm_node_with_tools(state: AgentState) -> AgentState:
    from lib.llm.litellm_api import call_llm_with_tools
    import json
    
    question = state["question"]
    query_context = state.get("query_context", [])
    
    prompt_entry = f"""
    分析用户问题并分类：
    
    用户问题：{question}
    用户之前的问答记录：{query_context}
    
    请使用 classify_query 工具进行分类和查询扩展。
    """
    
    # Define tools in OpenAI format (LiteLLM compatible)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "classify_query",
                "description": "Classify user query and generate expanded queries for RAG search",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": ["greeting", "insult", "unclear", "need_rag"],
                            "description": "Classification of the user query"
                        },
                        "expanded_queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Expanded queries for RAG search (1-3 queries, 15 chars max each)"
                        },
                        "answer": {
                            "type": "string",
                            "description": "Direct answer for greeting/insult/unclear types, empty for need_rag"
                        }
                    },
                    "required": ["query_type", "expanded_queries", "answer"]
                }
            }
        }
    ]
    
    # Call LLM with function calling via LiteLLM
    response = await call_llm_with_tools(
        prompt_entry,
        tools=tools,
        model_name="gpt",
        tool_choice="required"  # Force function call
    )
    
    # Parse function call result
    if response["tool_calls"]:
        tool_call = response["tool_calls"][0]
        function_args = json.loads(tool_call["function"]["arguments"])
        
        query_type = function_args["query_type"]
        expanded_queries = function_args["expanded_queries"]
        answer = function_args["answer"]
    else:
        # Fallback if no tool call (shouldn't happen with tool_choice="required")
        query_type = "unclear"
        expanded_queries = [question]
        answer = "抱歉，我无法理解您的问题，请重新表述。"
    
    # Update state based on classification
    if query_type == "need_rag":
        return {
            **state,
            "query_type": query_type,
            "search_ops": [{"type": "search_general", "query_list": expanded_queries}],
            "answer": ""
        }
    else:
        return {
            **state,
            "query_type": query_type,
            "answer": answer,
            "search_ops": []
        }
```

## Files to Modify

- `lib/llm/litellm_api.py` - Add tool calling support
- `lib/agentic/nodes/entry_llm_node.py` - Use tools instead of JSON Schema
- `lib/agentic/nodes/reply_validation_node.py` - Use tools for search operation generation
- `lib/rag/query_expand.py` - Use tools for query expansion

