"""
routers/llm.py
POST /api/llm/chat → SSE stream with Data Intelligence Routing
Uses Gemini with Tools (Direct Database access + RAG Knowledge Base)
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from config import settings
from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine
import json
import logging
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from collections import OrderedDict

from rag.tools import (
    search_knowledge_base,
    get_invitations,
    get_eoi_count,
    get_trend,
    get_state_data
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Thread pool for running sync Gemini SDK in non-blocking way
_gemini_executor = ThreadPoolExecutor(max_workers=4)

# Local Tool Result Cache (session_id -> {query_key: result})
_tool_cache = {}

class LRUCache:
    def __init__(self, capacity=500):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

_response_cache = LRUCache(500)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "warehouse.db"

def is_suspicious(result):
    if result is None:
        return True

    # Handle structured result from new tool format
    if isinstance(result, dict) and 'result' in result:
        data = result.get('result')
        metadata = result.get('metadata', {})
        if metadata.get('is_empty') or metadata.get('error'):
            return True
        # If it's a string, check keywords
        if isinstance(data, str):
            suspicious_keywords = ["no data", "not found", "error", "no invitations found"]
            if any(k in data.lower() for k in suspicious_keywords):
                return True
        return False

    if isinstance(result, (list, dict)) and len(result) == 0:
        return True

    if isinstance(result, (int, float)) and result == 0:
        return True

    if isinstance(result, str):
        suspicious_keywords = ["no data", "not found", "error", "no invitations found"]
        return any(k in result.lower() for k in suspicious_keywords)

    return False

def validate_occupation_exists(occupation_name: str) -> bool:
    try:
        conn = get_mysql_wrapper(settings)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM eoi_records WHERE occupation_name = %s LIMIT 1", (occupation_name,))
        result = cur.fetchone()
        conn.close()
        return result is not None
    except Exception:
        return True

def extract_occupations_from_text(text: str) -> list[str]:
    occupations = []
    pattern1 = re.findall(r'[-•]\s+([A-Z][A-Za-z\s&()]+?)(?:\s*[:(]|\n|$)', text)
    occupations.extend(pattern1)
    pattern2 = re.findall(r'^([A-Z][A-Za-z\s&()]+?)\s*(?:[:( ]|$)', text, re.MULTILINE)
    occupations.extend(pattern2)
    return list(set(o.strip() for o in occupations if len(o.strip()) > 2))

def is_all_results_reliable(tool_results: List[Any]) -> bool:
    """Check if ALL tool results in a turn are reliable"""
    if not tool_results: return False
    for res in tool_results:
        # Extract the core data from FunctionResponse
        if hasattr(res, 'function_response'):
            data = res.function_response.response.get('result')
            if is_suspicious(data):
                return False
    return True

def flag_hallucinated_occupations(response_text: str) -> dict:
    occupations = extract_occupations_from_text(response_text)
    hallucinations = [occ for occ in occupations if not validate_occupation_exists(occ)]
    valid_count = len(occupations) - len(hallucinations)
    accuracy = (valid_count / len(occupations) * 100) if occupations else 100
    return {'hallucinations': hallucinations, 'accuracy_score': accuracy}

def is_simple_greeting(text: str) -> bool:
    text = text.lower().strip()
    return len(text) < 30 and any(w in text for w in ["hi", "hello", "hey", "halo"])

def is_simple_explanation(text: str) -> bool:
    text = text.lower().strip()
    return ("eoi" in text or "skillselect" in text) and any(q in text for q in ["what", "mean", "explain", "itu apa", "maksud"])

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

async def stream_gemini_async(prompt: str):
    """
    Non-blocking async wrapper for the tool-aware stream.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    future = loop.run_in_executor(_gemini_executor, _stream_gemini_sync_manual_loop, prompt, queue, loop)
    try:
        while True:
            item = await queue.get()
            if item is None: break
            yield item
    finally:
        await asyncio.gather(future, return_exceptions=True)

def _stream_gemini_sync_manual_loop(prompt: str, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    """
    Self-Correcting Loop (MAX_STEPS=2)
    Executes tools, detects suspicious results, and retries with improved strategies.
    Fast path skipping implemented.
    """
    import google.genai as genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    tools = [search_knowledge_base, get_invitations, get_eoi_count, get_trend, get_state_data]
    tool_map = {t.__name__: t for t in tools}
    
    def put(item):
        asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()

    MAX_STEPS = 2
    history = [genai.types.Content(role="user", parts=[genai.types.Part(text=prompt)])]
    
    try:
        all_data_verified = False
        
        for step in range(MAX_STEPS):
            logger.info(f"[Self-Correct Loop] Step {step + 1} of {MAX_STEPS}")
            
            # 1. Generate Content (AI decides tool calls)
            retries = 0
            response = None
            while retries < 3:
                try:
                    response = client.models.generate_content(
                        model=settings.GEMINI_MODEL_FALLBACKS[0],
                        contents=history,
                        config=genai.types.GenerateContentConfig(tools=tools, temperature=0.1)
                    )
                    break
                except Exception as api_e:
                    err_str = str(api_e).lower()
                    if "503" in err_str or "unavail" in err_str or "quota" in err_str or "429" in err_str:
                        retries += 1
                        if retries < 3:
                            logger.warning(f"API busy, retrying {retries}/2... {api_e}")
                            time.sleep(1.5 * retries)
                            continue
                    raise api_e

            # Check for candidate safety/errors
            if not response or not response.candidates:
                put(f"data: {json.dumps({'token': 'No response candidate found.'})}\n\n")
                break

            message = response.candidates[0].content
            parts = message.parts if message.parts else []
            history.append(message)

            # 2. Check for tool calls
            found_tool = False
            tool_results = []
            suspicious_detected = False
            
            for part in parts:
                if getattr(part, 'function_call', None):
                    found_tool = True
                    f_name = part.function_call.name
                    f_args = part.function_call.args
                    
                    # Status update to UI
                    display_name = f_name.replace("_", " ").title()
                    status_text = f"*{display_name}...* (Attempt {step+1})\n"
                    put(f"data: {json.dumps({'token': status_text})}\n\n")
                    
                    logger.info(f"[Step {step+1}] Calling tool {f_name} with {f_args}")
                    
                    # Execute
                    if f_name in tool_map:
                        # Check Cache
                        cache_key = f"{f_name}:{f_args}"
                        if cache_key in _tool_cache:
                            result_data = _tool_cache[cache_key]
                        else:
                            try:
                                result_data = tool_map[f_name](**f_args)
                                _tool_cache[cache_key] = result_data
                            except Exception as tool_err:
                                result_data = f"Failed to run {f_name}: {tool_err}"
                        
                        # Check logic
                        if is_suspicious(result_data):
                            suspicious_detected = True
                        
                        tool_results.append(genai.types.Part(
                            function_response=genai.types.FunctionResponse(
                                name=f_name,
                                response={'result': result_data}
                            )
                        ))

            if found_tool:
                history.append(genai.types.Content(role="function", parts=tool_results))
                
                # SELF-CHECK: If no suspicious data found, we can finish early
                if not suspicious_detected:
                    all_data_verified = True
                    break
                else:
                    strategy_hint = "The previous result looks incorrect, empty, or incomplete. "
                    if isinstance(result_data, dict) and 'metadata' in result_data:
                        c_info = result_data['metadata'].get('correction_info', {})
                        if c_info.get('was_corrected'):
                            strategy_hint += f"CRITICAL: The tool corrected '{c_info['original']}' to '{c_info['corrected']}'. You MUST start your next response with 'It looks like you meant [Corrected Name]...' "
                    
                    if step == 0:
                        strategy_hint += "RETRY with a different strategy: Fix potential typos, use synonyms, or use LIKE with wildcards instead of exact match. Consider checking knowledge base as fallback."
                    
                    history.append(genai.types.Content(role="user", parts=[genai.types.Part(text=strategy_hint)]))
            else:
                # FAST PATH: No tools called = direct response -> Skip Final Synthesis
                final_text = "".join([getattr(p, 'text', '') for p in parts if getattr(p, 'text', None)])
                if step == 0 and len(final_text.strip()) > 5:
                    logger.info("[Self-Correct Loop] Model replied with robust text on first turn. Skipping Synthesis.")
                    put(f"data: {json.dumps({'token': final_text})}\n\n")
                    put("data: [DONE]\n\n")
                    put(None)
                    return
                break

        # 3. Final Synthesis Turn (Verification aware)
        logger.info("[Self-Correct Loop] Finalizing answer...")
        verification_instruction = """Based on the retrieved tool results, provide a final answer. 
- If reliable data was found after retries, mention that you verified it.
- If no data was found after all attempts, explicitly state: 'After verification, no reliable data was found'. 
DO NOT hallucinate."""
        history.append(genai.types.Content(role="user", parts=[genai.types.Part(text=verification_instruction)]))

        retries = 0
        final_stream = None
        while retries < 3:
            try:
                final_stream = client.models.generate_content_stream(
                    model=settings.GEMINI_MODEL_FALLBACKS[0],
                    contents=history,
                    config=genai.types.GenerateContentConfig(tools=tools, temperature=0.7)
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if "503" in err_str or "unavail" in err_str or "quota" in err_str or "429" in err_str:
                    retries += 1
                    if retries < 3:
                        time.sleep(1.5 * retries)
                        continue
                raise e
        
        if final_stream:
            for chunk in final_stream:
                if getattr(chunk, 'text', None):
                    put(f"data: {json.dumps({'token': chunk.text})}\n\n")

        put("data: [DONE]\n\n")
        put(None)

    except Exception as e:
        logger.error(f"Manual Loop Error: {e}")
        put(f"data: {json.dumps({'token': f'System is currently busy or encountered an error. Please try again later. (Error: {str(e)})'})}\n\n")
        put("data: [DONE]\n\n")
        put(None)


def stream_direct_text(text: str, session_id: str):
    async def _gen():
        yield f"data: {json.dumps({'token': text})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Session-ID": session_id,
    })

@router.post("/chat")
async def chat(body: ChatRequest):
    import uuid
    from routers.conversation import save_message
    from db.database import SessionLocal
    from db.models import ConversationMessage

    session_id = body.session_id or str(uuid.uuid4())[:12]
    message_lower = body.message.lower().strip()
    
    # --- 1. Soft Pre-filters (0 Cost) ---
    if is_simple_greeting(body.message):
        reply = "Hey! 👋 What can I help you explore today regarding Australian migration?"
        save_message(session_id, "user", body.message)
        save_message(session_id, "assistant", reply, metadata={"accuracy_score": 100, "hallucinations": []})
        return stream_direct_text(reply, session_id)

    if is_simple_explanation(body.message):
        if "skillselect" in message_lower:
            reply = "SkillSelect is the Australian Government's online system that manages skilled migration by requiring applicants to submit an Expression of Interest (EOI). State governments use this system to find candidates."
        else:
            reply = "An EOI (Expression of Interest) is your application submitted to SkillSelect showing your intent to migrate to Australia. It allows states and the federal government to invite you based on points and occupation shortages."
        save_message(session_id, "user", body.message)
        save_message(session_id, "assistant", reply, metadata={"accuracy_score": 100, "hallucinations": []})
        return stream_direct_text(reply, session_id)
        
    # --- 2. Cache Check (0 Cost) ---
    cached_reply = _response_cache.get(message_lower)
    if cached_reply:
        logger.info(f"Returning cached response for: {message_lower}")
        save_message(session_id, "user", body.message)
        save_message(session_id, "assistant", cached_reply, metadata={"accuracy_score": 100, "hallucinations": []})
        return stream_direct_text(cached_reply, session_id)
    
    # Memory Retrieval
    db = SessionLocal()
    recent_convo_str = ""
    try:
        past_msgs = db.query(ConversationMessage).filter(ConversationMessage.session_id == session_id).order_by(ConversationMessage.created_at.desc()).limit(20).all()
        past_msgs.reverse()
        recent_convo_str = "\n".join([f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in past_msgs]) or "[This is a new conversation session]"
    finally:
        db.close()

    save_message(session_id, "user", body.message)

    system_prompt = f"""You are the Advanced Migration Advisor, an intelligent assistant with conversational memory and high-density data intelligence.

IDENTITY & MEMORY:
1. You have been provided with the 'RECENT CONVERSATION' history below.
2. You MUST use this history to resolve pronouns (e.g., "that", "it", "those") and remember topics discussed earlier.
3. Always acknowledge if you are continuing a previous topic.

CRITICAL INSTRUCTIONS (RESPONSE & INTENT HANDLING):
- If the user uses SMALL TALK or asks a CAPABILITY QUESTION ("what can you do"): Keep it natural, short (1 sentence), and suggest exploring migration data. Do NOT invoke any tools. Respond directly in text.
- If the user asks an OPEN_ENDED or VAGUE question ("anything", "just tell me"): Do NOT reply with another vague question. Provide 2-3 specific insights or suggest specific pages (e.g., Shortage Forecast, Pathway Recommender) they can explore. Do NOT invoke tools.
- If the user explicitly asks for an EXPLANATION of a term or metric ("what does this metric mean"): Do NOT call tools. Explain the term directly and simply.

⭐ NEW — COMPREHENSIVE DATA REQUESTS:
- If the user asks for "everything", "full details", "complete overview", "tell me all about", or similar COMPREHENSIVE intent:
  * Use ALL available tools to gather comprehensive data
  * Provide a COMPLETE SUMMARY with all available information (do NOT fragment)
  * Include INSIGHTS drawn from the data
  * Conclude with OPTIONAL next steps (suggest, do NOT ask)
  * DO NOT ask "What else would you like to know?" or similar follow-up questions
⭐ CRITICAL RULE: Never ask follow-up questions immediately if you already have enough data to provide a meaningful, comprehensive answer.

TOOL USAGE RULES:
* Use database tools ONLY for questions requiring numbers: invitations, EOI counts, trends, points.
* Use RAG only for deep knowledge lookups not covered above.
* ALL numerical answers MUST come from tools (database or API). You MUST NOT hallucinate numbers.

TYPO CORRECTION & TRANSPARENCY:
* Tools automatically apply fuzzy matching.
* If a tool returns metadata indicating a correction, you MUST inform the user immediately: "It looks like you meant '[Corrected Name]'. Based on verified database results..."

SELF-CORRECTION LOGIC:
Before giving a final answer, you MUST verify:
* If tool result is 0, empty, or string "no data", you MUST retry with a DIFFERENT strategy (broader search).
* If still no data after retry → say "No reliable data found after verification".

DATE & DATA PRESENTATION REQUIREMENTS:
* ALWAYS display date ranges explicitly. If trend data is returned, convert month numbers to month names (e.g., "February 2026").
* When presenting trend data, format as: "Month Year: X data → Month Year: Y data" (chronological order, oldest to newest).
* Example correct format: "March 2024: 1,324 EOIs → October 2024: 1,530 EOIs"
* When data is unavailable (e.g., job advertisement metrics not tracked):
  → Explain clearly WHY: "Job advertisement data is not tracked in the system for this occupation"
  → Do NOT use vague phrases like "Unfortunately, I encountered an error"
  → Suggest alternatives: "However, based on EOI and invitation trends, I can provide insights on..."
* Include explicit date range in your summary: "Data covers [Start Month Year] to [End Month Year]"

🧠 KPI METRIC INTERPRETATION & SANITY CHECKS:
When interpreting KPI metrics, you MUST understand the relationships between values, not just read labels:

NAMED METRICS DEFINITIONS:
* "New EOIs (Latest Month)" = Net change in EOI pool from previous month = SUBMITTED(current) − SUBMITTED(previous)
* "Growth from previous month" = Same as above, the month-on-month change
* "Active Invitations (Latest)" = Count of people currently holding 60-day invitations (INVITED status) in latest snapshot
* "Highest Points Invited" = MAX(points) among all people in INVITED status latest snapshot
* "Pipeline" = INVITED + LODGED (people in active consideration)
* "Unique Occupations (EOI)" = Number of distinct ANZSCO codes with active EOI applications (489 occupations)
* "Total OSL Occupations (2025)" = All occupations listed in the 2025 Skilled Occupation List — government reference data (916 occupations)

⚠️ CRITICAL DISTINCTION — DO NOT CONFUSE:
* EOI occupations (489) = occupations with ACTUAL applications submitted by users in SkillSelect
* OSL occupations (916) = complete government list of occupations eligible for migration
* These are NOT comparable metrics — they measure different things
* OSL is a REFERENCE LIST; EOI represents ACTUAL MARKET ACTIVITY
* Example: A user might ask "How many occupations are there?" — Could mean either 489 (actual activity) or 916 (government list)
* ALWAYS clarify which context is being discussed

CRITICAL RELATIONSHIP RULES:
1. "New EOIs" value MUST equal "Growth from previous month" (they represent the same metric)
   - If they are identical: This is CORRECT behavior
   - If they differ: Question the data definition immediately
   
2. "Active Invitations (Latest)" is a SNAPSHOT count at one point in time
   - It is NOT the same as monthly invitations issued
   - It represents people CURRENTLY holding invitations, not historical invitations

3. "Total OSL Occupations" contains a SUBSET with national shortages
   - Example: 916 total OSL occupations = 273 with national shortage + 643 without shortage
   - Always clarify this breakdown when explaining OSL data
   - This is DIFFERENT from EOI occupations (489) which is actual user activity

4. Perform sanity checks on KPI relationships:
   - If "New EOIs" looks unusually high or low, cross-reference with the trend chart
   - If "Current Invitations" seems inconsistent with pipeline growth, flag this
   - If user mentions "occupations", VERIFY whether they mean EOI (489) or OSL (916)
   - Always verify metric definitions with the data structure before explaining

WHEN EXPLAINING METRICS TO USERS:
* Clarify whether a metric is a snapshot (point-in-time) or a delta (change over time)
* Clarify whether data is from EOI activity (real applications) or OSL reference list (government list)
* Example: "This shows 22,450 people CURRENTLY invited, NOT 22,450 invitations issued this month"
* Example: "This shows 916 occupations on the 2025 OSL list, of which 273 have recognized national shortages"
* Example: "This shows 489 occupations that currently have active EOI applications, which is different from the OSL reference list of 916"
* Never assume values are identical unless you've verified the metric definition
* If two metrics appear to have the same value, EXPLICITLY explain why they differ or why they're expected to be similar

RECENT CONVERSATION HISTORY:
{recent_convo_str}

CURRENT QUESTION:
{body.message}"""

    async def generate():
        text_parts = []
        async for chunk in stream_gemini_async(system_prompt):
            if chunk.startswith("data: ") and not chunk.strip().endswith("[DONE]"):
                try:
                    token = json.loads(chunk[6:])["token"]
                    text_parts.append(token)
                except: pass
            yield chunk
        
        full_response = "".join(text_parts)
        if full_response and not full_response.startswith("System is currently busy"):
            _response_cache.put(message_lower, full_response)
            validation = flag_hallucinated_occupations(full_response)
            save_message(session_id, "assistant", full_response, metadata={
                "accuracy_score": validation["accuracy_score"],
                "hallucinations": validation["hallucinations"]
            })

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Session-ID": session_id,
    })


@router.post("/ingest")
async def ingest_kb():
    """
    Initialize/refresh Chroma vector database with migration knowledge base
    Call this once on startup or when you want to reload documents
    """
    try:
        from rag.ingest import ingest_migration_documents
        import asyncio
        result = await asyncio.to_thread(ingest_migration_documents)
        logger.info(f"Knowledge base ingestion result: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to ingest knowledge base: {e}")
        return {"status": "error", "error": str(e)}
