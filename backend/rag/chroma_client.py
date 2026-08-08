"""
rag/chroma_client.py
Vector database (Chroma) client for RAG — Migration data retrieval
"""
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def sanitize_metadata_value(value):
    """Convert metadata value to ChromaDB-safe type (str, int, float, bool)"""
    if value is None:
        return ""
    elif isinstance(value, bool):
        return value
    elif isinstance(value, (int, float)):
        return value
    elif isinstance(value, str):
        return value
    else:
        return str(value)


def sanitize_metadata(metadata: dict):
    """Sanitize all metadata values for ChromaDB compatibility"""
    if not metadata:
        return {}
    return {k: sanitize_metadata_value(v) for k, v in metadata.items()}


# Initialize Chroma client (persistent storage)
CHROMA_DIR = Path(__file__).resolve().parent.parent / "data" / "chroma"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    
    # Use fast local embedding model instead of API (10x faster)
    # all-MiniLM-L6-v2: 384-dim embeddings, ~2-3 min for 4200 docs
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    logger.info("✓ Using local sentence-transformer model for embeddings (all-MiniLM-L6-v2)")
    
    # Persistent client with local embeddings
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(
            anonymized_telemetry=False,
            is_persistent=True,
        )
    )
    logger.info(f"Chroma client initialized at {CHROMA_DIR}")
except Exception as e:
    logger.error(f"Failed to initialize Chroma: {e}")
    client = None
    embedding_fn = None


def get_or_create_collection(name: str = "migration-docs"):
    """Get or create a Chroma collection for migration documents"""
    if not client:
        raise RuntimeError("Chroma client not initialized")
    
    try:
        collection = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_fn
        )
        logger.info(f"Collection '{name}' ready with {collection.count()} documents")
        return collection
    except ValueError as ve:
        # Expected error: Embedding function conflict: new: sentence_transformer vs persisted: default
        logger.warning(f"Embedding function conflict detected, attempting fallback: {ve}")
        collection = client.get_collection(name=name)
        logger.warning(f"Continuing with persisted embedding function. Collection '{name}' ready with {collection.count()} documents")
        return collection
    except Exception as e:
        logger.error(f"Failed to get/create collection: {e}")
        raise


def add_documents(collection, documents: list[dict]):
    """
    Add documents to Chroma collection
    
    Args:
        collection: Chroma collection object
        documents: List of dicts with 'id', 'text', 'metadata' keys
    
    Example:
        documents = [
            {
                'id': 'visa_189_1',
                'text': 'Visa 189 is a skilled migration visa for points-tested applicants...',
                'metadata': {'category': 'visa_types', 'source': 'official'}
            }
        ]
    """
    try:
        # ChromaDB has a max batch size (currently 5461). We chunk it to 5,000 for safety.
        CHUNK_SIZE = 5000
        total_docs = len(documents)
        
        for i in range(0, total_docs, CHUNK_SIZE):
            chunk = documents[i:i + CHUNK_SIZE]
            ids = [d['id'] for d in chunk]
            texts = [d['text'] for d in chunk]
            metadatas = [sanitize_metadata(d.get('metadata', {})) for d in chunk]
            
            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            logger.info(f"Added chunk {i//CHUNK_SIZE + 1}/{(total_docs-1)//CHUNK_SIZE + 1} ({len(chunk)} docs)")
            
        logger.info(f"Successfully added total {total_docs} documents to collection")
        return True
    except Exception as e:
        logger.error(f"Failed to add documents: {e}")
        raise


def query_documents_with_scores(collection, query: str, n_results: int = 5) -> tuple[list[str], list[float]]:
    """
    Query Chroma collection for relevant documents with cosine distance scores.
    
    Returns:
        Tuple of (document texts, distances). Distance near 0 = very relevant, near 2 = not relevant.
    """
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "distances"]
        )
        
        documents = []
        distances = []
        if results and results['documents'] and len(results['documents']) > 0:
            documents = results['documents'][0]
            distances = results['distances'][0] if results.get('distances') else [1.0] * len(documents)
        
        logger.info(f"Query returned {len(documents)} documents with distances {distances}")
        return documents, distances
    except Exception as e:
        logger.error(f"Failed to query documents: {e}")
        return [], []


def query_documents_by_category(collection, query: str, category: str, n_results: int = 100) -> tuple[list[str], list[float]]:
    """
    Query Chroma collection filtering by metadata category.
    
    Args:
        collection: Chroma collection
        query: Search query text
        category: Metadata category filter (e.g., 'occupations')
        n_results: Number of results to return (default 100 for all occupations)
    
    Returns:
        Tuple of (document texts, distances)
    """
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"category": category},
            include=["documents", "distances"]
        )
        
        documents = []
        distances = []
        if results and results['documents'] and len(results['documents']) > 0:
            documents = results['documents'][0]
            distances = results['distances'][0] if results.get('distances') else [1.0] * len(documents)
        
        logger.info(f"Category query (category={category}) returned {len(documents)} documents")
        return documents, distances
    except Exception as e:
        logger.error(f"Failed to query documents by category: {e}")
        return [], []


def query_documents(collection, query: str, n_results: int = 5) -> list[str]:
    """Legacy wrapper — returns only document texts."""
    docs, _ = query_documents_with_scores(collection, query, n_results)
    return docs


def clear_collection(collection):
    """Clear all documents from collection (for reset/rebuild)"""
    try:
        count = collection.count()
        collection.delete(where={"id": {"$ne": ""}})  # Delete all
        logger.info(f"Cleared {count} documents from collection")
    except Exception as e:
        logger.error(f"Failed to clear collection: {e}")
