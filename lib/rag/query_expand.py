import keyword
from lib.llm.litellm_api import call_llm_with_fallback, call_llm_with_tools
from lib.app_logger import get_logger
import json

logger = get_logger(__name__)

class QueryExpander:
    def __init__(self):
        pass
    
    async def expand(self, 
                     query:str, 
                     query_context:list[str]=[], 
                     k:int=1
    ) -> list[str]:
        prompt = f"""
        猜测用户的提问意图，并给出一个更具体的查询问句，15个字以内。
        例如：
        用户提问：如何做好人
        扩展：一个人应具备哪些道德品格，如何加以实践与培养
        扩展：{k}个不同的查询问句
        以下是用户之前的问答记录：{query_context}
        用户当前提问：{query}
        
        请使用 expand_queries 工具进行查询扩展。
        """
        
        # Define tools for query expansion
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "expand_queries",
                    "description": "Expand user query into more specific search queries",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "queries": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                                "maxItems": k,
                                "description": "List of expanded queries (15 chars max each)"
                            }
                        },
                        "required": ["queries"]
                    }
                }
            }
        ]
        
        try:
            # Call LLM with function calling
            response = await call_llm_with_tools(
                prompt,
                tools=tools,
                model_name="gemini",
                tool_choice="required"
            )
            
            # Parse function call result
            if response["tool_calls"]:
                tool_call = response["tool_calls"][0]
                function_args = json.loads(tool_call["function"]["arguments"])
                queries = function_args.get("queries", [])
                logger.info("Expanded queries (function calling): %s", queries)
                return queries
            else:
                # Fallback to structured output
                return await self._expand_with_structured_output(prompt, k)
        except Exception as e:
            # Fallback to structured output on error
            logger.warning(f"Function calling failed, falling back to structured output: {e}")
            return await self._expand_with_structured_output(prompt, k)
    
    async def _expand_with_structured_output(self, prompt: str, k: int) -> list[str]:
        """Fallback method using structured output."""
        json_schema = {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": k
                }
            },
            "required": ["queries"]
        }
        
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "query_expansion_schema",
                "schema": json_schema
            }
        }
        
        respond = await call_llm_with_fallback(prompt, 
                                               model_name="gemini", 
                                               response_format=response_format)
        
        logger.info("Respond (structured output): %s", respond)
        
        # Parse the structured response (litellm returns JSON string when using structured output)
        try:
            parsed_dict = json.loads(respond) if isinstance(respond, str) else respond
            return parsed_dict.get("queries", [])
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to parse structured output: {e}")
            return []
