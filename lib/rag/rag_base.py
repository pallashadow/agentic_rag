import json
import copy
import textwrap
import asyncio

from lib.search.elastic_mix import ElasticMix
from lib.mcp import SearchService, GeneralSearchRequest, NaiveSearchRequest
from lib.rag.query_expand import QueryExpander
from lib.rag.rag_prompt import build_rag_prompt, PROMPT_BASE
from lib.language_detect import detect_query_lang
from lib.llm.litellm_api import call_llm_with_fallback, call_llm_stream_with_fallback
from lib.app_logger import get_logger

logger = get_logger(__name__)

class RAGBase:
    def __init__(self):
        # Initialize ElasticMix only for MCP layer - not used directly
        self.elastic_mix = ElasticMix()
        self.search_service = SearchService(self.elastic_mix)
        self.prompt_base = PROMPT_BASE
        self.prompt_before = self.prompt_base["prompt1"]
        self.prompt_after = self.prompt_base["prompt2"]
        self.query_expander = QueryExpander()
        self.max_query_expand_k = 3
        self.max_chunk_k = 12
        
    
    async def search(self, query:str, 
                     chunk_index:str,
                     query_context:list[str]=[], 
                     title_k:int=3, 
                     chunk_k:int=10, 
                     query_expand_k:int=0,
                     doc_lang: str = "zh",
                     query_lang: str = "zh",
        ) -> tuple[list[dict], list[str]]:
        query_expand_k = min(query_expand_k, self.max_query_expand_k)
        chunk_k = min(chunk_k, self.max_chunk_k)
        
        search_results = []
        query_list = [query]
        expanded_query = []
        if query_expand_k > 0:
            expanded_query = await self.query_expander.expand(
                query,
                query_context,
                k=query_expand_k,
                prompt_lang=doc_lang,
                doc_lang=doc_lang,
                query_lang=query_lang,
            )
            logger.info("Expanded Query: %s", expanded_query)
            query_list += expanded_query
            chunk_k = chunk_k // 2
        
        # Use MCP layer instead of direct elastic_mix call
        # title_index is automatically derived from chunk_index in MCP layer
        mcp_request = GeneralSearchRequest(
            query_list=query_list,
            chunk_index=chunk_index,
            top_k=chunk_k,
            title_k=title_k
        )
        doc_results = await self.search_service.general_search(mcp_request)
        
        # Convert DocumentResult to dict format for compatibility
        search_results = [
            {
                "doc_id": r.doc_id,
                "chunk_id": r.chunk_id,
                "text": r.text,
                "doc_title": r.doc_title,
                "score": r.score,
                "index": r.index
            }
            for r in doc_results
        ]
        
        return search_results, expanded_query
    
    async def search_naive(self, query: str, chunk_index: str, chunk_k: int = 10) -> list[dict]:
        """Naive search - direct chunk search without title filtering or query expansion."""
        # Use MCP layer instead of direct elastic_mix call
        mcp_request = NaiveSearchRequest(
            query=query,
            chunk_index=chunk_index,
            top_k=chunk_k
        )
        doc_results = await self.search_service.naive_search(mcp_request)
        
        # Convert DocumentResult to dict format for compatibility
        return [
            {
                "doc_id": r.doc_id,
                "chunk_id": r.chunk_id,
                "text": r.text,
                "doc_title": r.doc_title,
                "score": r.score,
                "index": r.index
            }
            for r in doc_results
        ]
    
    async def chat(self, query:str, 
                   chunk_index:str,
                   query_context:list[str]=[], 
                   title_k:int=3, 
                   chunk_k:int=10, 
                   query_expand_k:int=1,
                   prompt_before:str=None,
                   prompt_after:str=None,
                   query_lang: str = "zh",
                   doc_lang: str = "zh",
    ) -> tuple[str, list[dict], str]:
        if not query_lang:
            query_lang = detect_query_lang(query)
        # step 1: search
        search_results, expanded_queries = await self.search(
            query,
            chunk_index,
            query_context,
            title_k=title_k,
            chunk_k=chunk_k,
            query_expand_k=query_expand_k,
            doc_lang=doc_lang,
            query_lang=query_lang,
        )
        
        # step 2: generate prompt
        prompt = build_rag_prompt(
            query,
            search_results,
            query_context,
            prompt_before,
            prompt_after,
            prompt_lang=query_lang,
        )
        
        # step 3: call LLM
        llm_response = await call_llm_with_fallback(prompt, model_name="gpt")
        
        logger.info("Query Context: %s", "\n".join(query_context))
        logger.info("Query: %s", query)
        logger.info("LLM Response: %s", textwrap.fill(llm_response, width=50))
        # Convert search results to text only for logging to avoid NameError.
        try:
            search_results_txt = json.dumps(search_results, ensure_ascii=False)
        except TypeError:
            search_results_txt = str(search_results)
        logger.info("Search Results: %s", textwrap.fill(search_results_txt, width=50))
        logger.info("LLM Prompt: %s", textwrap.fill(prompt, width=50))
        
        result = {
            "content": llm_response,
            "search_results": search_results,
            "prompt": prompt, 
            "querys": [query] + expanded_queries,
        }
        return result
    
    async def chat_stream(self, query:str, 
                         chunk_index:str,
                         query_context:list[str]=[], 
                         title_k:int=3, 
                         chunk_k:int=10, 
                         query_expand_k:int=1,
                         prompt_before:str=None,
                         prompt_after:str=None,
                         query_lang: str = "zh",
                         doc_lang: str = "zh",
    ):
        """
        Stream RAG chat response as async generator.
        
        Yields:
            dict: Response chunks with keys:
                - type: "search" | "content" | "metadata" | "done"
                - data: chunk data (str for content, dict for others)
        """
        if not query_lang:
            query_lang = detect_query_lang(query)
        # step 1: search (don't yield results, they're too large)
        search_results, expanded_queries = await self.search(
            query,
            chunk_index,
            query_context,
            title_k=title_k,
            chunk_k=chunk_k,
            query_expand_k=query_expand_k,
            doc_lang=doc_lang,
            query_lang=query_lang,
        )
        
        # step 2: generate prompt
        prompt = build_rag_prompt(
            query,
            search_results,
            query_context,
            prompt_before,
            prompt_after,
            prompt_lang=query_lang,
        )
        
        # step 3: stream LLM response only (don't yield search results or metadata immediately)
        full_content = ""
        async for chunk in call_llm_stream_with_fallback(prompt, model_name="gpt"):
            full_content += chunk
            yield {
                "type": "content",
                "data": chunk
            }
        
        # Log final response
        logger.info("Query Context: %s", "\n".join(query_context))
        logger.info("Query: %s", query)
        logger.info("LLM Response: %s", textwrap.fill(full_content, width=50))
        
        # Yield completion with all data (search results will be shown in collapsed details at the end)
        yield {
            "type": "done",
            "data": {
                "content": full_content,
                "search_results": search_results,
                "prompt": prompt,
                "querys": [query] + expanded_queries,
            }
        }