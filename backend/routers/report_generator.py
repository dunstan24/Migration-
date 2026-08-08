"""
routers/report_generator.py - SPRINT 5
Auto-generate narrative reports using Gemini AI + RAG context
"""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import json

from config import settings
from rag.chroma_client import query_documents, get_or_create_collection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportRequest(BaseModel):
    occupation: Optional[str] = None
    visa_type: Optional[str] = None  # 189, 190, 491
    state: Optional[str] = None
    focus: str = "comprehensive"  # comprehensive, shortage, future_outlook, strategy


async def generate_narrative_with_gemini(prompt: str) -> str:
    """
    Generate narrative text using Gemini AI
    Returns streaming or complete response
    """
    if not settings.GEMINI_API_KEY:
        return "[Mock Report — add GEMINI_API_KEY to use AI generation]"
    
    import google.genai as genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    # Try each available model
    for model_name in settings.GEMINI_MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=1500
                ),
            )
            
            if response.text:
                logger.info(f"Report generated with model: {model_name}")
                return response.text
                
        except Exception as e:
            logger.warning(f"Model {model_name} failed for report: {str(e)[:100]}")
            continue
    
    return "[Report generation failed - all models unavailable]"


@router.post("/generate-narrative", summary="Generate occupation narrative report")
async def generate_occupation_narrative(request: ReportRequest):
    """
    Generate a comprehensive narrative report for an occupation.
    Combines RAG data with Gemini AI to create migration advice narrative.
    
    Report includes:
    - Occupation overview and demand
    - Visa pathway recommendations (189/190/491)
    - Points strategy (age, experience, English, qualifications)
    - State sponsorship opportunities
    - Timeline and processing expectations
    - Success factors and tips
    """
    
    if not request.occupation:
        raise HTTPException(status_code=400, detail="occupation parameter required")
    
    try:
        occ_name = request.occupation
        logger.info(f"Generating report for: {occ_name}")
        
        # Retrieve relevant context from RAG
        collection = get_or_create_collection("migration-docs")
        
        # Get occupation data
        occ_results = query_documents(collection, occ_name, n_results=3)
        shortage_results = query_documents(collection, f"{occ_name} shortage", n_results=2)
        projection_results = query_documents(collection, f"{occ_name} employment growth", n_results=2)
        
        # Get visa info if specified
        visa_context = ""
        if request.visa_type:
            visa_results = query_documents(collection, f"Visa {request.visa_type}", n_results=1)
            visa_context = "".join(visa_results) if visa_results else ""
        
        # Get state info if specified
        state_context = ""
        if request.state:
            state_results = query_documents(collection, f"{request.state} sponsorship", n_results=1)
            state_context = "".join(state_results) if state_results else ""
        
        # Build prompt for Gemini
        prompt = f"""You are a skilled migration advisor for Inter Studies. Generate a comprehensive migration report narrative for this occupation:

OCCUPATION: {occ_name}
{"VISA TYPE: " + request.visa_type if request.visa_type else ""}
{"STATE: " + request.state if request.state else ""}
REPORT FOCUS: {request.focus}

KNOWN DATA ABOUT THIS OCCUPATION:
{json.dumps(occ_results[:2]) if occ_results else "No specific data available"}

SHORTAGE & DEMAND INFO:
{json.dumps(shortage_results[:1]) if shortage_results else "No shortage data available"}

FUTURE OUTLOOK:
{json.dumps(projection_results[:1]) if projection_results else "No projection data available"}

{f"VISA PATHWAY INFO: {visa_context}" if visa_context else ""}
{f"STATE SPONSORSHIP: {state_context}" if state_context else ""}

Based on this data, write a 2-3 paragraph narrative report that includes:
1. Current demand and shortage status
2. Recommended visa pathway (189/190/491) with rationale
3. Estimated points requirements and strategy
4. Key advantages and success factors
5. Timeline expectations
6. Action items for the applicant

Write in professional but accessible language. Be specific about points and timeframes. Include realistic success probability considerations."""

        # Generate narrative
        narrative = await generate_narrative_with_gemini(prompt)
        
        return {
            "occupation": occ_name,
            "visa_type": request.visa_type,
            "state": request.state,
            "focus": request.focus,
            "report": narrative,
            "generated_at": "2026-04-06",
            "source": "Migration Advisor AI"
        }
        
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-strategy", summary="Generate personalized migration strategy")
async def generate_strategy(
    occupation: str = Query(..., description="Your occupation"),
    age: int = Query(..., ge=18, le=65),
    years_experience: int = Query(..., ge=0, le=50),
    english_level: str = Query("proficient", enum=["competent", "proficient", "superior"]),
    qualifications: str = Query(..., description="e.g., 'Bachelor in IT' or 'Trade in Electrician'"),
    visa_preference: Optional[str] = Query(None, enum=["189", "190", "491"])
):
    """
    Generate personalized migration strategy based on applicant profile.
    Uses RAG data to provide realistic advice.
    """
    
    try:
        # Retrieve occupation and visa data
        collection = get_or_create_collection("migration-docs")
        occ_results = query_documents(collection, occupation, n_results=4)
        points_results = query_documents(collection, "points system age English experience", n_results=2)
        
        # Calculate estimated points
        age_points = 30 if 25 <= age <= 32 else (25 if 33 <= age <= 39 else 20)
        english_points = {"competent": 0, "proficient": 10, "superior": 20}[english_level]
        exp_points = 20 if years_experience >= 8 else (15 if years_experience >= 5 else 10)
        qual_points = 15
        
        total_points = age_points + english_points + exp_points + qual_points
        
        prompt = f"""You are a skilled migration strategy advisor. Create a personalized migration strategy for this applicant:

PROFILE:
- Occupation: {occupation}
- Age: {age}
- Work Experience: {years_experience} years
- English Level: {english_level}
- Qualifications: {qualifications}
- Visa Preference: {visa_preference or "Open to all (189/190/491)"}

ESTIMATED POINTS: {total_points} (Age: {age_points}, English: {english_points}, Experience: {exp_points}, Qualifications: {qual_points})

OCCUPATION DATA:
{json.dumps(occ_results) if occ_results else ""}

Based on this profile, write a personalized strategy that includes:
1. Current competitiveness (estimated competition level for this occupation)
2. Recommended visa pathway
3. Timeline expectations
4. Immediate action items
5. Risk factors and mitigation
6. Success probability (realistic estimate)

Be specific and actionable. Consider current market conditions and competition."""

        strategy = await generate_narrative_with_gemini(prompt)
        
        return {
            "occupation": occupation,
            "profile": {
                "age": age,
                "years_experience": years_experience,
                "english_level": english_level,
                "qualifications": qualifications
            },
            "estimated_points": total_points,
            "visa_preference": visa_preference,
            "strategy": strategy,
            "generated_at": "2026-04-06"
        }
        
    except Exception as e:
        logger.error(f"Strategy generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
