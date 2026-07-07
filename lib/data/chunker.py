import os
import re
import tiktoken
from tqdm import tqdm
from lib.data.files import load_whitelist_names

class NaiveChunker:
    def __init__(self, 
                 input_dir="./data_miles/documents/", 
                 output_dir="./data_miles/chunks/", 
                 chunk_size=500,
                 chunk_overlap=100,
                 reload=False,
                 encoding="cl100k_base",
                 writelist_file=None, # whitelist files to process
                 limit=None, # limit the number of files to process
                 skip_existing=True, # skip existing chunks files
                 strip_headers=True, # strip miles-specific header/footer markers
                 ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.reload = reload
        self.writelist_file = writelist_file
        self.limit = limit
        self.skip_existing = skip_existing
        # miles_guo documents carry a "内容梗概:" header and a Gnews footer that
        # must be stripped. Non-Chinese corpora (e.g. hansard) have neither, so
        # allow callers to disable the strip rather than branching on dataset name.
        self.strip_headers = strip_headers
        # Initialize tiktoken encoder for token-based chunking
        self.encoding = tiktoken.get_encoding(encoding)

    def run(self):
        """Process all files in input_dir and save chunks to output_dir"""
        # Create output directory if it doesn't exist
        if not os.path.isdir(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Read whitelist once so filtering is deterministic and cheap during traversal.
        whitelist_names = load_whitelist_names(self.writelist_file)

        # Get all files from input directory
        files = [os.path.join(self.input_dir, f) for f in os.listdir(self.input_dir)
                 if os.path.isfile(os.path.join(self.input_dir, f))]

        # If whitelist is provided and not empty, only process whitelisted files.
        if whitelist_names:
            files = [f for f in files if os.path.basename(f) in whitelist_names]

        # Optionally limit file count for quick experiments or partial runs.
        if self.limit is not None:
            files = files[:max(0, int(self.limit))]
        
        # Process each file
        for file_path in tqdm(files, desc="Chunking files"):
            try:
                # Get base filename without extension
                base_name = os.path.basename(file_path)
                doc_id = os.path.splitext(base_name)[0]
                
                # Keep backward compatibility: reload=True means always reprocess.
                should_skip_existing = self.skip_existing and not self.reload

                # Check if first chunk file exists and skip when configured.
                first_chunk_file = os.path.join(self.output_dir, f"{doc_id}_1.txt")
                if should_skip_existing and os.path.exists(first_chunk_file):
                    continue
                
                # Get chunks from the file
                chunks = self.load_data_to_paragraphs(file_path)
                
                # Save each chunk as a separate file
                for i, chunk in enumerate(chunks, start=1):
                    chunk_id = i
                    output_file = os.path.join(self.output_dir, f"{doc_id}_{chunk_id}.txt")
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(chunk)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

    def load_data_to_paragraphs(self, file1):
        """Split long document into short documents using token-based chunking.
        Because OpenAI sentence embedding ada-002 has 8000 input tokens, maximum 2000 Chinese characters.
        However, semantic encoding effectiveness decreases when approaching 2000 characters.
        
        Uses tiktoken for token-based splitting, which provides better control over LLM token limits.
        """
        with open(file1, "r", encoding="utf-8") as f:
            data = f.read()
        if self.strip_headers:
            pattern1 = r'^.*?内容梗概: '
            pattern2 = r' 友情链接：Gnews \| Gclubs \| Gfashion \| himalaya exchange \| gettr \| 法治基金 \| 新中国联邦辞典 \| $'
            data = re.sub(pattern1, "", data)
            data = re.sub(pattern2, "", data)
        
        # Convert character-based sizes to approximate token counts
        # For Chinese text, roughly 1.5-2 characters per token
        # We'll encode a sample to estimate, then use token-based chunking
        sample_tokens = self.encoding.encode(data[:min(1000, len(data))])
        if len(sample_tokens) > 0:
            chars_per_token = min(1000, len(data)) / len(sample_tokens)
            max_tokens = int(self.chunk_size / chars_per_token)
            overlap_tokens = int(self.chunk_overlap / chars_per_token)
        else:
            # Fallback if encoding fails
            max_tokens = self.chunk_size // 2
            overlap_tokens = self.chunk_overlap // 2
        
        # Ensure minimum values
        max_tokens = max(50, max_tokens)
        overlap_tokens = max(0, min(overlap_tokens, max_tokens // 2))
        
        # Token-based chunking with overlap
        txts = self._chunk_by_tokens(data, max_tokens, overlap_tokens)
        return txts
    
    def _chunk_by_tokens(self, text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
        """Split text into chunks based on token count with overlap support.
        
        Args:
            text: Text to split
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Number of tokens to overlap between chunks
        
        Returns:
            List of text chunks
        """
        # Encode the entire text into tokens
        tokens = self.encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return [text]
        
        chunks = []
        start_idx = 0
        
        while start_idx < len(tokens):
            # Get tokens for this chunk
            end_idx = min(start_idx + max_tokens, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            
            # Decode tokens back to text
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # Move start index forward, accounting for overlap
            if end_idx >= len(tokens):
                break
            start_idx = end_idx - overlap_tokens
        
        return chunks