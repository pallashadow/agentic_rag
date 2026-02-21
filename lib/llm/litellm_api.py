import litellm
from litellm import acompletion
from pydantic import BaseModel
import asyncio
import nest_asyncio
import os
import logging
from litellm import Router
import json
import time
from lib.observability.langsmith import (
    langsmith_enabled,
    traced,
    create_trace_metadata,
    update_trace_with_token_usage,
)
nest_asyncio.apply()
import tempfile
litellm.enable_json_schema_validation=True

# Suppress LiteLLM INFO logs
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
# Also disable LiteLLM's verbose logging
litellm.set_verbose = False

# Create a single shared router instance to avoid callback limit issues
_router = None

def get_litellm_fallback_router():
    """Get or create a shared router instance"""
    global _router
    if _router is None:
        _router = Router(
            model_list=[
                #{
                #    "model_name": "claude", 
                #    "litellm_params": {
                #        "model": "anthropic/claude-3-haiku-20240307"}
                #}, 
                {
                    "model_name": "gpt",
                    "litellm_params": {
                        "model": "openai/gpt-4o-mini", 
                    }
                },
                {
                    "model_name": "gemini",
                    "litellm_params": {
                        "model": "gemini/gemini-2.0-flash-001", 
                    }
                }
            ],
            fallbacks=[{"gpt": ["gemini"]}, {"gemini":["gpt"]}],
            num_retries=1,
            max_fallbacks=1, 
        )
    return _router

async def call_llm_with_fallback(str1, 
                                 model_name = "gemini", 
                                 response_format=None
                                 ):
    router = get_litellm_fallback_router()
    kwargs = {"temperature": 0.0}
    result = await call_llm(
        str1, 
        router, 
        model_name, 
        response_format, 
        kwargs
    )
    return result

@traced(run_type="llm", name="call_llm")
async def call_llm(str1, 
                   router=None, 
                   model_name="openai/gpt-4o", 
                   response_format=None, 
                   kwargs={}):
    start_time = time.time()
    
    # Add metadata if LangSmith is enabled
    if langsmith_enabled():
        try:
            response_format_type = response_format.get("type") if response_format else None
            metadata = create_trace_metadata(
                model_name=model_name,
                response_format=response_format_type,
            )
        except Exception:
            pass
    
    acompletion1 = router.acompletion if router else acompletion
    response = await acompletion1(
        model=model_name,
        messages=[{"role": "user", "content": str1}], 
        response_format=response_format, 
        **kwargs, 
    )
    
    latency = time.time() - start_time
    
    x = response.choices[0].message.content
    
    # Parse JSON string when using structured output (response_format with json_schema)
    # litellm returns JSON string when using structured output, need to parse it
    if response_format and response_format.get("type") == "json_schema":
        try:
            return json.loads(x)
        except (json.JSONDecodeError, TypeError) as e:
            logging.warning(f"Failed to parse structured output as JSON: {e}. Returning raw string.")
    
    # Record latency and token usage if available
    if langsmith_enabled():
        try:
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            if hasattr(response, "usage"):
                if hasattr(response.usage, "prompt_tokens"):
                    prompt_tokens = response.usage.prompt_tokens
                if hasattr(response.usage, "completion_tokens"):
                    completion_tokens = response.usage.completion_tokens
                if hasattr(response.usage, "total_tokens"):
                    total_tokens = response.usage.total_tokens
            
            # Update LangSmith trace with token usage
            # This ensures token counts are properly tracked in LangSmith UI
            update_trace_with_token_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency=latency,
            )
        except Exception as e:
            logging.debug(f"Failed to record token usage to LangSmith: {e}")
            
    return x

@traced(run_type="llm", name="call_llm_stream")
async def call_llm_stream(str1, 
                         router=None, 
                         model_name="openai/gpt-4o", 
                         response_format=None, 
                         kwargs={}):
    """
    Stream LLM response as async generator yielding chunks.
    
    Yields:
        str: Content chunks from the LLM stream
    """
    start_time = time.time()
    
    # Add metadata if LangSmith is enabled
    if langsmith_enabled():
        try:
            response_format_type = response_format.get("type") if response_format else None
            metadata = create_trace_metadata(
                model_name=model_name,
                response_format=response_format_type,
            )
        except Exception:
            pass
    
    acompletion1 = router.acompletion if router else acompletion
    stream = await acompletion1(
        model=model_name,
        messages=[{"role": "user", "content": str1}], 
        response_format=response_format,
        stream=True,
        **kwargs, 
    )
    
    async for chunk in stream:
        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    
    # Record latency
    if langsmith_enabled():
        try:
            latency = time.time() - start_time
            metadata = create_trace_metadata(latency=latency)
        except Exception:
            pass

@traced(run_type="llm", name="call_llm_stream_with_fallback")
async def call_llm_stream_with_fallback(str1, 
                                        model_name="gpt", 
                                        response_format=None):
    """
    Stream LLM response with fallback support.
    
    Yields:
        str: Content chunks from the LLM stream
    """
    router = get_litellm_fallback_router()
    kwargs = {"temperature": 0.0}
    
    # Add metadata if LangSmith is enabled
    if langsmith_enabled():
        try:
            response_format_type = response_format.get("type") if response_format else None
            metadata = create_trace_metadata(
                model_name=model_name,
                response_format=response_format_type,
                fallback_triggered=False,
            )
        except Exception:
            pass
    
    try:
        async for chunk in call_llm_stream(
            str1, 
            router, 
            model_name, 
            response_format, 
            kwargs
        ):
            yield chunk
    except Exception as e:
        # If primary model fails, try fallback
        fallback_model = "gemini" if model_name == "gpt" else "gpt"
        logging.warning(f"Primary model {model_name} failed, trying fallback {fallback_model}: {e}")
        
        # Record fallback in trace
        if langsmith_enabled():
            try:
                metadata = create_trace_metadata(
                    fallback_triggered=True,
                    fallback_model=fallback_model,
                )
            except Exception:
                pass
        
        try:
            async for chunk in call_llm_stream(
                str1, 
                router, 
                fallback_model, 
                response_format, 
                kwargs
            ):
                yield chunk
        except Exception as fallback_error:
            logging.error(f"Both models failed: {fallback_error}")
            raise

@traced(run_type="llm", name="call_llm_with_tools")
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
    start_time = time.time()
    
    # Add metadata if LangSmith is enabled
    if langsmith_enabled():
        try:
            metadata = create_trace_metadata(
                model_name=model_name,
                tool_count=len(tools) if tools else 0,
                tool_choice=tool_choice,
            )
        except Exception:
            pass
    
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
    
    latency = time.time() - start_time
    
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
    
    # Record latency and token usage if available
    if langsmith_enabled():
        try:
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            if hasattr(response, "usage"):
                if hasattr(response.usage, "prompt_tokens"):
                    prompt_tokens = response.usage.prompt_tokens
                if hasattr(response.usage, "completion_tokens"):
                    completion_tokens = response.usage.completion_tokens
                if hasattr(response.usage, "total_tokens"):
                    total_tokens = response.usage.total_tokens
            
            # Update LangSmith trace with token usage
            update_trace_with_token_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency=latency,
            )
        except Exception as e:
            logging.debug(f"Failed to record token usage to LangSmith: {e}")
    
    return result