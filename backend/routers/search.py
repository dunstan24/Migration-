"""
routers/search.py - SPRINT 5
Semantic occupation search + RAG-enhanced search
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional
import logging

from rag.chroma_client import query_documents, get_or_create_collection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


class SearchResult(BaseModel):
    id: str
    text: str
    category: str
    occupation: Optional[str] = None
    score: Optional[float] = None
    metadata: dict = {}


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResult]


@router.get("/occupations", response_model=SearchResponse, summary="Semantic occupation search")
async def search_occupations(q: str = Query(..., min_length=2, description="Search query (occupation name, keywords, skillsearch, etc.)")):
    """
    Semantic search for occupations and related migration data.
    Uses ChromaDB vector search to find relevant documents.
    
    Examples:
    - /api/search/occupations?q=software+engineer
    - /api/search/occupations?q=healthcare+shortage
    - /api/search/occupations?q=visa+191+regional
    - /api/search/occupations?q=NSW+sponsored+jobs
    """
    try:
        collection = get_or_create_collection("migration-docs")
        
        # Query ChromaDB - returns top 10 most relevant documents
        results = collection.query(
            query_texts=[q],
            n_results=10,
            include=["documents", "metadatas", "distances"]
        )
        
        search_results = []
        
        if results and results['documents'] and len(results['documents']) > 0:
            for i, (doc_text, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                # Convert distance to similarity score (0-1, where 1 is most similar)
                # Cosine distance ranges from 0-2, where 0 is identical
                similarity = 1 - (distance / 2)
                
                search_results.append(SearchResult(
                    id=metadata.get('id', f'result_{i}'),
                    text=doc_text[:300],  # Truncate for response
                    category=metadata.get('category', 'general'),
                    occupation=metadata.get('occupation', None),
                    score=round(similarity, 3),
                    metadata=metadata
                ))
        
        logger.info(f"Search for '{q}' returned {len(search_results)} results")
        
        return SearchResponse(
            query=q,
            total_results=len(search_results),
            results=search_results
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return SearchResponse(
            query=q,
            total_results=0,
            results=[],
        )


@router.get("/occupations/{occ_name}", summary="Get detailed occupation info")
async def get_occupation_details(occ_name: str):
    """
    Get comprehensive information about a specific occupation.
    Retrieves shortage status, employment projections, points data, EOI statistics.
    """
    try:
        collection = get_or_create_collection("migration-docs")
        
        # Search for this occupation specifically
        results = collection.query(
            query_texts=[occ_name],
            n_results=15,
            include=["documents", "metadatas", "distances"],
            where={"category": {"$in": ["occupations", "shortage", "projections"]}}
        )
        
        occupation_data = {
            "occupation_name": occ_name,
            "shortage_info": None,
            "projections": None,
            "eoi_stats": None,
            "documents": []
        }
        
        if results and results['documents'] and len(results['documents']) > 0:
            for doc_text, metadata in zip(results['documents'][0], results['metadatas'][0]):
                
                if metadata.get('category') == 'shortage':
                    occupation_data["shortage_info"] = {
                        "status": metadata.get('shortage_status'),
                        "year": metadata.get('year'),
                        "text": doc_text
                    }
                    
                elif metadata.get('category') == 'projections':
                    occupation_data["projections"] = {
                        "growth_5yr": metadata.get('growth_5yr'),
                        "sector": metadata.get('sector'),
                        "text": doc_text
                    }
                    
                elif metadata.get('category') == 'occupations':
                    occupation_data["eoi_stats"] = {
                        "eoi_count": metadata.get('eoi_count'),
                        "avg_points": metadata.get('avg_points'),
                        "text": doc_text
                    }
                
                occupation_data["documents"].append({
                    "category": metadata.get('category'),
                    "text": doc_text[:200],
                    "metadata": metadata
                })
        
        logger.info(f"Retrieved details for {occ_name}")
        return occupation_data
        
    except Exception as e:
        logger.error(f"Error retrieving occupation {occ_name}: {e}")
        return {"error": str(e), "occupation": occ_name}


@router.get("/visa-info", summary="Search visa information")
async def search_visa_info(q: str = Query(..., min_length=2)):
    """
    Search for visa-related information (189, 190, 491, processing, sponsorship, etc.)
    """
    try:
        collection = get_or_create_collection("migration-docs")
        
        results = collection.query(
            query_texts=[q],
            n_results=5,
            include=["documents", "metadatas"],
            where={"category": {"$in": ["visa_types", "eoi_skillselect", "state_sponsorship", "visa_processing"]}}
        )
        
        visa_info = []
        
        if results and results['documents'] and len(results['documents']) > 0:
            for doc_text, metadata in zip(results['documents'][0], results['metadatas'][0]):
                visa_info.append({
                    "category": metadata.get('category'),
                    "visa": metadata.get('visa'),
                    "text": doc_text,
                    "metadata": metadata
                })
        
        return {
            "query": q,
            "results": visa_info
        }
        
    except Exception as e:
        logger.error(f"Visa search error: {e}")
        return {"query": q, "results": [], "error": str(e)}
