"""
LangSmith tracing helper module.

Provides unified tracing utilities for LangSmith observability integration.
Centralizes metadata tags and tracing behavior to keep business code clean.
"""
import os
import logging
from typing import Optional, Dict, Any
from functools import wraps

try:
    from langsmith import traceable
    from langsmith.run_helpers import tracing_context
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    # Create a no-op decorator if langsmith is not available
    def traceable(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator
    def tracing_context():
        from contextlib import nullcontext
        return nullcontext()


def langsmith_enabled() -> bool:
    """Check if LangSmith tracing is enabled via environment variables."""
    if not LANGSMITH_AVAILABLE:
        return False
    return (
        os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
        and bool(os.getenv("LANGSMITH_API_KEY"))
    )


def get_metadata_tags() -> Dict[str, str]:
    """
    Get standard metadata tags for all traces.
    
    Returns:
        Dictionary of tags to attach to traces (env, version, service)
    """
    return {
        "env": os.getenv("APP_ENV", "unknown"),
        "version": os.getenv("APP_VERSION", "unknown"),
        "service": "chatbot-milesguo",
    }


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata to remove sensitive information before logging.
    
    Args:
        metadata: Raw metadata dictionary
        
    Returns:
        Sanitized metadata with sensitive fields masked or removed
    """
    sanitized = metadata.copy()
    
    # Mask API keys and tokens
    sensitive_keys = ["api_key", "token", "password", "secret"]
    for key in sanitized:
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
    
    # Optionally trim long content
    max_content_length = 1000
    for key, value in sanitized.items():
        if isinstance(value, str) and len(value) > max_content_length:
            sanitized[key] = value[:max_content_length] + "...[truncated]"
    
    return sanitized


def traced(run_type: str = "chain", name: Optional[str] = None):
    """
    Decorator factory for tracing functions with LangSmith.
    
    Args:
        run_type: Type of run (e.g., "chain", "tool", "llm")
        name: Optional name for the trace (defaults to function name)
        
    Returns:
        Decorator that wraps the function with tracing if enabled
    """
    if not langsmith_enabled():
        def passthrough(fn):
            return fn
        return passthrough
    
    def decorator(fn):
        # Use function name if name not provided
        trace_name = name or fn.__name__
        
        @traceable(run_type=run_type, name=trace_name)
        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)
        
        @traceable(run_type=run_type, name=trace_name)
        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        
        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(fn):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def create_trace_metadata(
    endpoint: Optional[str] = None,
    chunk_index: Optional[str] = None,
    title_k: Optional[int] = None,
    chunk_k: Optional[int] = None,
    query_expand_k: Optional[int] = None,
    has_context: Optional[bool] = None,
    model_name: Optional[str] = None,
    response_format: Optional[str] = None,
    tool_count: Optional[int] = None,
    tool_choice: Optional[str] = None,
    max_iter: Optional[int] = None,
    search_count: Optional[int] = None,
    query_type: Optional[str] = None,
    fallback_triggered: Optional[bool] = None,
    fallback_model: Optional[str] = None,
    **extra_metadata
) -> Dict[str, Any]:
    """
    Create standardized metadata dictionary for traces.
    
    Args:
        endpoint: API endpoint name
        chunk_index: Elasticsearch chunk index name
        title_k: Number of title results
        chunk_k: Number of chunk results
        query_expand_k: Query expansion multiplier
        has_context: Whether query context was provided
        model_name: LLM model identifier
        response_format: Response format type (json_schema, etc.)
        tool_count: Number of tools provided
        tool_choice: Tool choice strategy
        max_iter: Maximum iterations for agentic loop
        search_count: Actual number of searches performed
        query_type: Query classification type
        fallback_triggered: Whether fallback was used
        fallback_model: Fallback model name
        **extra_metadata: Additional metadata fields
        
    Returns:
        Dictionary of metadata ready for trace attachment
    """
    metadata = {}
    
    # API-level metadata
    if endpoint:
        metadata["endpoint"] = endpoint
    if chunk_index:
        metadata["chunk_index"] = chunk_index
    if title_k is not None:
        metadata["title_k"] = title_k
    if chunk_k is not None:
        metadata["chunk_k"] = chunk_k
    if query_expand_k is not None:
        metadata["query_expand_k"] = query_expand_k
    if has_context is not None:
        metadata["has_context"] = has_context
    
    # LLM-level metadata
    if model_name:
        metadata["model_name"] = model_name
    if response_format:
        metadata["response_format"] = response_format
    if tool_count is not None:
        metadata["tool_count"] = tool_count
    if tool_choice:
        metadata["tool_choice"] = tool_choice
    
    # Agentic/Graph-level metadata
    if max_iter is not None:
        metadata["max_iter"] = max_iter
    if search_count is not None:
        metadata["search_count"] = search_count
    if query_type:
        metadata["query_type"] = query_type
    
    # Fallback metadata
    if fallback_triggered is not None:
        metadata["fallback_triggered"] = fallback_triggered
    if fallback_model:
        metadata["fallback_model"] = fallback_model
    
    # Add any extra metadata
    metadata.update(extra_metadata)
    
    # Sanitize before returning
    return sanitize_metadata(metadata)


def update_trace_with_token_usage(
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    latency: Optional[float] = None,
    **extra_metadata
) -> None:
    """
    Update the current LangSmith trace with token usage information.
    This is needed because LiteLLM doesn't automatically integrate with LangSmith's token tracking.
    
    LangSmith expects token information in the 'extra' field of a run. This function attempts to
    update the current active run with token usage data.
    
    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        total_tokens: Total number of tokens
        latency: Request latency in seconds
        **extra_metadata: Additional metadata to attach
    """
    if not langsmith_enabled() or not LANGSMITH_AVAILABLE:
        return
    
    try:
        from langsmith import Client
        
        # Prepare token usage data in LangSmith's expected format
        run_extra = {}
        
        # LangSmith recognizes these keys for token tracking
        if prompt_tokens is not None:
            run_extra["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            run_extra["completion_tokens"] = completion_tokens
        if total_tokens is not None:
            run_extra["total_tokens"] = total_tokens
        if latency is not None:
            run_extra["latency"] = latency
        
        # Add any extra metadata
        run_extra.update(extra_metadata)
        
        if not run_extra:
            return
        
        # Try to get the current run_id from the traceable context
        # LangSmith's traceable decorator stores run info in contextvars
        try:
            import contextvars
            # Access the run_id from the current context
            # The traceable decorator should have set this up
            run_id = None
            
            # Try to get from active context
            try:
                # Check if there's a run_id in the current context
                # This is set by LangSmith's traceable decorator
                ctx = contextvars.copy_context()
                # Look for LangSmith's internal context variable
                # Note: This is implementation-dependent and may need adjustment
                for key in dir(ctx):
                    if 'run' in key.lower() or 'trace' in key.lower():
                        try:
                            value = getattr(ctx, key)
                            if isinstance(value, str) and len(value) > 10:  # Likely a UUID
                                run_id = value
                                break
                        except Exception:
                            pass
            except Exception:
                pass
            
            # If we found a run_id, update the run
            if run_id:
                client = Client()
                client.update_run(
                    run_id=run_id,
                    extra=run_extra,
                )
            else:
                # Fallback: log token info (will appear in trace metadata if available)
                logging.debug(f"Token usage recorded but run_id not available: {run_extra}")
        except Exception as e:
            logging.debug(f"Failed to update LangSmith trace with token usage: {e}")
    except Exception as e:
        # Silently fail to avoid breaking the main flow
        logging.debug(f"Failed to update LangSmith trace with token usage: {e}")

