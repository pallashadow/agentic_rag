"""
Unit tests for LiteLLM function calling support.
Tests the call_llm_with_tools function and its integration with nodes.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json


@pytest.fixture
def mock_router():
    """Mock LiteLLM router for testing."""
    router = AsyncMock()
    
    # Mock response object structure
    mock_message = Mock()
    mock_message.content = None
    mock_message.tool_calls = []
    
    mock_choice = Mock()
    mock_choice.message = mock_message
    
    mock_response = Mock()
    mock_response.choices = [mock_choice]
    
    router.acompletion = AsyncMock(return_value=mock_response)
    return router


@pytest.fixture
def mock_router_with_tool_call():
    """Mock LiteLLM router that returns function call."""
    router = AsyncMock()
    
    # Create mock tool call
    mock_function = Mock()
    mock_function.name = "test_function"
    mock_function.arguments = json.dumps({"key": "value"})
    
    mock_tool_call = Mock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function = mock_function
    
    mock_message = Mock()
    mock_message.content = None
    mock_message.tool_calls = [mock_tool_call]
    
    mock_choice = Mock()
    mock_choice.message = mock_message
    
    mock_response = Mock()
    mock_response.choices = [mock_choice]
    
    router.acompletion = AsyncMock(return_value=mock_response)
    return router


@pytest.mark.asyncio
async def test_call_llm_with_tools_no_tool_calls(mock_router):
    """Test call_llm_with_tools when LLM returns no tool calls."""
    from lib.llm.litellm_api import call_llm_with_tools, get_litellm_fallback_router
    
    with patch("lib.llm.litellm_api.get_litellm_fallback_router", return_value=mock_router):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_function",
                    "description": "Test function",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        
        result = await call_llm_with_tools(
            "Test prompt",
            tools=tools,
            model_name="gpt",
            tool_choice="auto"
        )
        
        assert result["content"] == ""
        assert result["tool_calls"] == []
        mock_router.acompletion.assert_called_once()
        call_kwargs = mock_router.acompletion.call_args[1]
        assert call_kwargs["tools"] == tools
        assert call_kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_call_llm_with_tools_with_tool_call(mock_router_with_tool_call):
    """Test call_llm_with_tools when LLM returns a tool call."""
    from lib.llm.litellm_api import call_llm_with_tools, get_litellm_fallback_router
    
    with patch("lib.llm.litellm_api.get_litellm_fallback_router", return_value=mock_router_with_tool_call):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_function",
                    "description": "Test function",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        
        result = await call_llm_with_tools(
            "Test prompt",
            tools=tools,
            model_name="gpt",
            tool_choice="required"
        )
        
        assert result["content"] == ""
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_123"
        assert result["tool_calls"][0]["function"]["name"] == "test_function"
        assert result["tool_calls"][0]["function"]["arguments"] == '{"key": "value"}'


@pytest.mark.asyncio
async def test_call_llm_with_tools_with_content(mock_router):
    """Test call_llm_with_tools when LLM returns content."""
    from lib.llm.litellm_api import call_llm_with_tools
    
    # Update mock to return content
    mock_message = Mock()
    mock_message.content = "Test response"
    mock_message.tool_calls = None
    
    mock_choice = Mock()
    mock_choice.message = mock_message
    
    mock_response = Mock()
    mock_response.choices = [mock_choice]
    
    mock_router.acompletion = AsyncMock(return_value=mock_response)
    
    with patch("lib.llm.litellm_api.get_litellm_fallback_router", return_value=mock_router):
        result = await call_llm_with_tools(
            "Test prompt",
            tools=[],
            model_name="gpt"
        )
        
        assert result["content"] == "Test response"
        assert result["tool_calls"] == []


@pytest.mark.asyncio
async def test_entry_llm_node_with_function_calling():
    """Test entry_llm_node using function calling."""
    from lib.agentic.nodes.entry_llm_node import entry_llm_node
    from lib.agentic.config import get_agent_state_default
    
    # Mock function calling response
    mock_response = {
        "content": "",
        "tool_calls": [{
            "id": "call_123",
            "function": {
                "name": "classify_query",
                "arguments": json.dumps({
                    "query_type": "need_rag",
                    "expanded_queries": ["expanded query 1", "expanded query 2"],
                    "answer": ""
                })
            }
        }]
    }
    
    state = get_agent_state_default()
    state["question"] = "What is the capital of France?"
    
    with patch("lib.agentic.nodes.entry_llm_node.call_llm_with_tools", new_callable=AsyncMock, return_value=mock_response):
        result = await entry_llm_node(state)
        
        assert result["query_type"] == "need_rag"
        assert result["answer"] == ""
        assert result["search_ops"] is not None
        assert len(result["search_ops"]) > 0


@pytest.mark.asyncio
async def test_entry_llm_node_fallback_to_structured_output():
    """Test entry_llm_node falls back to structured output when function calling fails."""
    from lib.agentic.nodes.entry_llm_node import entry_llm_node
    from lib.agentic.config import get_agent_state_default
    
    state = get_agent_state_default()
    state["question"] = "What is the capital of France?"
    
    # Mock function calling to raise exception
    mock_function_calling = AsyncMock(side_effect=Exception("Function calling failed"))
    
    # Mock structured output fallback
    mock_structured_output = {
        "query_type": "need_rag",
        "expanded_queries": ["expanded query"],
        "answer": ""
    }
    
    with patch("lib.agentic.nodes.entry_llm_node.call_llm_with_tools", side_effect=mock_function_calling), \
         patch("lib.agentic.nodes.entry_llm_node.call_llm_with_fallback", new_callable=AsyncMock, return_value=mock_structured_output), \
         patch("lib.agentic.nodes.entry_llm_node.get_entry_prompt_and_format", return_value=("prompt", {})):
        result = await entry_llm_node(state)
        
        assert result["query_type"] == "need_rag"
        assert result["answer"] == ""


@pytest.mark.asyncio
async def test_reply_validation_node_with_function_calling():
    """Test reply_validation_node using function calling."""
    from lib.agentic.nodes.reply_validation_node import reply_validation_node
    from lib.agentic.config import get_agent_state_default
    
    # Mock function calling response
    mock_response = {
        "content": "",
        "tool_calls": [{
            "id": "call_123",
            "function": {
                "name": "validate_and_refine",
                "arguments": json.dumps({
                    "type_state": "valid_answer",
                    "search_ops": [],
                    "valid_search_indices": [1, 2]
                })
            }
        }]
    }
    
    state = get_agent_state_default()
    state["question"] = "Test question"
    state["answer"] = "Test answer"
    state["search_results"] = [{"index": 1}, {"index": 2}]
    state["search_count"] = 1
    
    with patch("lib.agentic.nodes.reply_validation_node.call_llm_with_tools", new_callable=AsyncMock, return_value=mock_response), \
         patch("lib.agentic.nodes.reply_validation_node.render_prompt", return_value="Test prompt"):
        result = await reply_validation_node(state)
        
        assert result["search_ops"] == []
        assert result["answer"] == "Test answer"


@pytest.mark.asyncio
async def test_query_expander_with_function_calling():
    """Test QueryExpander using function calling."""
    from lib.rag.query_expand import QueryExpander
    
    # Mock function calling response
    mock_response = {
        "content": "",
        "tool_calls": [{
            "id": "call_123",
            "function": {
                "name": "expand_queries",
                "arguments": json.dumps({
                    "queries": ["expanded query 1", "expanded query 2"]
                })
            }
        }]
    }
    
    expander = QueryExpander()
    
    with patch("lib.rag.query_expand.call_llm_with_tools", new_callable=AsyncMock, return_value=mock_response):
        result = await expander.expand("test query", [], k=2)
        
        assert len(result) == 2
        assert "expanded query 1" in result
        assert "expanded query 2" in result


@pytest.mark.asyncio
async def test_query_expander_fallback_to_structured_output():
    """Test QueryExpander falls back to structured output when function calling fails."""
    from lib.rag.query_expand import QueryExpander
    
    expander = QueryExpander()
    
    # Mock function calling to raise exception
    mock_function_calling = AsyncMock(side_effect=Exception("Function calling failed"))
    
    # Mock structured output fallback
    mock_structured_output = {"queries": ["fallback query"]}
    
    with patch("lib.rag.query_expand.call_llm_with_tools", side_effect=mock_function_calling), \
         patch("lib.rag.query_expand.call_llm_with_fallback", new_callable=AsyncMock, return_value=mock_structured_output):
        result = await expander.expand("test query", [], k=1)
        
        assert len(result) == 1
        assert "fallback query" in result

