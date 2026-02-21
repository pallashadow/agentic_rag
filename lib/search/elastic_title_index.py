import os
import json
from tqdm import tqdm
from lib.search.elastic_base import ElasticWriteClientBase, ElasticReadClientBase
from lib.app_logger import get_logger
logger = get_logger(__name__)


class ElasticWriteClientTitles(ElasticWriteClientBase):
    def __init__(self, 
                 title_index_name="miles_guo_titles",
                 title_path=None,
                 summaries_path=None,
                 ):
        """
        Initialize Elasticsearch client for indexing document titles and summaries.
        
        Args:
            title_index_name: Name of the Elasticsearch index for titles
            title_path: Path to JSON file containing document titles. If None, doc_title field will not be added.
            summaries_path: Path to JSON file containing document summaries. If None, doc_summary field will not be added.
        
        Note:
            At least one of title_path or summaries_path must be provided when calling insert_titles().
        """
        super().__init__(title_index_name)
        self.title_path = title_path
        self.summaries_path = summaries_path
            
    def clear_index(self):
        """
        Delete and recreate the Elasticsearch index with updated mappings.
        
        This method is used to reset the index completely, removing all existing documents
        and applying fresh mappings. Useful for reindexing or fixing mapping issues.
        
        Returns:
            bool: True if successful
        """
        try:
            self.client.indices.delete(index=self.index_name)
        except Exception as e:
            logger.exception("Error clearing index %s", self.index_name)
        self.client.indices.create(index=self.index_name)
        self.update_mappings()
        logger.info("Index %s cleared and mappings updated", self.index_name)
        return True
    
    def update_mappings(self, mappings=None):
        """
        Update Elasticsearch index mappings for title documents.
        
        Defines the field types for the index. If no mappings are provided,
        uses default mappings with doc_id (keyword), doc_summary (text), 
        doc_title (text), and question1 (text) fields.
        
        Args:
            mappings: Optional custom mappings dictionary. If None, uses default mappings.
        
        Returns:
            dict: Response from Elasticsearch put_mapping operation
        """
        if mappings is None:
            mappings = {
                "properties": {
                    "doc_id": {
                        "type": "keyword"
                    },
                    "doc_summary": {
                        "type": "text"
                    },
                    "doc_title": {
                        "type": "text"
                    },
                    "question1": {
                        "type": "text"
                    }
                }
            }
        mapping_response = self.client.indices.put_mapping(
            index=self.index_name, 
            body=mappings
        )
        return mapping_response
    
        
    def insert_titles(self, limit=None, skip_existing=True):
        """
        Insert document titles and summaries into Elasticsearch index.
        
        Loads titles and/or summaries from JSON files and indexes them in batches.
        Only includes fields for which corresponding paths were provided during initialization.
        Documents are indexed with doc_id, doc_title (if title_path provided), 
        doc_summary (if summaries_path provided), and question1 fields.
        
        Args:
            limit: Maximum number of documents to process. If None, processes all documents.
            skip_existing: If True, skips documents that already exist in the index.
        
        Raises:
            ValueError: If both title_path and summaries_path are None.
        
        Note:
            At least one of title_path or summaries_path must have been provided during initialization.
        """
        # Load summaries if summaries_path is provided
        if self.summaries_path is not None:
            with open(self.summaries_path, "r", encoding="utf-8") as f:
                self.summaries = json.load(f)
        else:
            self.summaries = {}
        
        # Load titles if title_path is provided
        if self.title_path is not None:
            with open(self.title_path, "r", encoding="utf-8") as f:
                self.titles = json.load(f)
        else:
            self.titles = {}
        
        # At least one path must be provided
        if not self.titles and not self.summaries:
            raise ValueError("At least one of title_path or summaries_path must be provided")
        
        # Use titles as primary source if available, otherwise use summaries
        source_dict = self.titles if self.titles else self.summaries
        
        # Check which documents already exist
        existing_ids = set()
        if skip_existing:
            existing_ids = self.get_existing_ids()
        
        batch_size = 100
        batch = []
        processed = 0
        skipped = 0
        
        # Calculate total items for progress bar
        total_items = len(source_dict)
        if limit:
            total_items = min(total_items, limit)
        
        for doc_id, value in tqdm(source_dict.items(), desc="Inserting titles", total=total_items):
            if limit and processed >= limit:
                break
            if skip_existing and doc_id in existing_ids:
                skipped += 1
                continue
            
            # Build document with only available fields
            doc = {
                "_id": doc_id,
                "doc_id": doc_id,
                "question1": ""
            }
            
            # Add doc_title if title_path is provided
            if self.title_path is not None:
                doc["doc_title"] = self.titles.get(doc_id, "")
            
            # Add doc_summary if summaries_path is provided
            if self.summaries_path is not None:
                summary = self.summaries.get(doc_id, None)
                if not summary:
                    print(f"Summary not found for document {doc_id}")
                    summary = ""
                doc["doc_summary"] = summary
            
            batch.append(doc)
            processed += 1
            if len(batch) >= batch_size:
                self.insert_doc(batch)
                batch = []
        if batch:
            self.insert_doc(batch)
        
        print(f"Inserted {processed} documents, skipped {skipped} existing documents")
        
        

class ElasticReadClientTitles(ElasticReadClientBase):
    def __init__(self):
        """
        Initialize Elasticsearch read client for searching document titles.
        
        This client is used for querying the title index without write operations.
        """
        super().__init__()

    async def search_title_naive(self, 
                                 query:str, 
                                 index_name:str, 
                                 k:int = 10, 
        ) -> list[dict]:
        """
        Search document titles and summaries using multi-match query.
        
        Performs a naive search across doc_summary (weighted 2x) and doc_title fields,
        returning results sorted by relevance score in descending order.
        
        Args:
            query: Search query string to match against titles and summaries
            index_name: Name of the Elasticsearch index to search
            k: Number of top results to return (default: 10)
            
        Returns:
            list[dict]: List of document dictionaries with added 'score' field, 
                       sorted by relevance score (descending)
        
        Raises:
            ValueError: If index_name is None
        """
        if index_name is None:
            raise ValueError("index_name is required")
        
        query_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "doc_summary^2",
                        "doc_title"
                    ]
                }
            },
            "size": k,
            "sort": ["_score"]  # Explicitly sort by score (descending is default)
        }
        search_response = await self.async_client.search(
            index=index_name,
            body=query_body
        )
        hits = search_response["hits"]["hits"]
        results = []
        for hit in hits:
            result = hit["_source"].copy()
            result["score"] = hit["_score"]
            results.append(result)
        return results
        
        