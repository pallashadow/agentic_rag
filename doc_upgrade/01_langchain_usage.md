# Current LangChain Usage

## langchain-text-splitters (Minimal Dependency)

**Location**: `lib/data/chunker.py`

**Current Usage**:
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

**Status**: This is the ONLY LangChain dependency in the project. It's used only for text chunking during data preparation.

## Replacement Options

### 1. **Keep it** (Recommended for now)
- Minimal dependency, well-maintained
- Good Chinese text handling
- No heavy LangChain ecosystem overhead

### 2. **Replace with `tiktoken`-based chunking**
- More control over token-based splitting
- Better for LLM token limits
- Example:
```python
import tiktoken
def chunk_by_tokens(text, max_tokens=500, encoding="cl100k_base"):
    encoding = tiktoken.get_encoding(encoding)
    tokens = encoding.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i:i+max_tokens]
        chunks.append(encoding.decode(chunk_tokens))
    return chunks
```

### 3. **Custom semantic chunking**
- Use sentence transformers for semantic boundaries
- Better chunk coherence for RAG

