"""
routers/llm.py
POST /api/llm/chat â†’ SSE stream with Data Intelligence Routing
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
    pattern1 = re.findall(r'[-â€¢]\s+([A-Z][A-Za-z\s&()]+?)(?:\s*[:(]|\n|$)', text)
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

def handle_small_talk_llm(message: str) -> str:
    """Uses LLM to fast-path small talk or reject if complex query."""
    import google.genai as genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    prompt = f"""You are a friendly AI migration advisor.

Your job is to understand the user's intent and respond naturally. The user may use informal, misspelled, or repeated-letter words. You must still understand the intent correctly.

Classify the user message into ONE of these categories:

1. SMALL_TALK:
- Greetings or casual conversation
- Examples: hi, hello, hey, yo, sup, what's up, halo, hai
- Repeated letters: hellooo, hiiii, heyyyy
- Polite greetings: good morning, good evening

2. CAPABILITY_QUESTION:
- Asking what you can do or what the system offers
- Asking about available data, jobs, or features
- Examples:
  - what can you do
  - how can you help
  - what jobs are available
  - what data do you have
  - what is this website
  - what information can I get here

3. OPEN_ENDED:
- The user gives vague responses like:
  "anything", "whatever", "just tell me", "idk", "you decide"

4. EXPLANATION_QUESTION:
- The user is asking what something means
- Not asking for data, but for explanation/definition
- Examples:
  - what is EOI
  - what does this metric mean
  - what is "New EOIs (Latest Month)"
  - explain this dashboard item

5. NOT_SMALL_TALK:
- Any real question about data, migration, jobs, invitations, etc.

---

Response Rules:

If SMALL_TALK:
- Respond naturally like a human
- Keep it short (1 sentence)
- Ask a light follow-up question

If CAPABILITY_QUESTION:
- Briefly explain what you can help with (1 sentence)
- Mention jobs, invitations, or migration data
- Ask what the user is interested in

If OPEN_ENDED:
- Do NOT ask another vague question
- Take initiative
- Suggest 2â€“3 specific things the user can explore
- Keep it natural and helpful
- Vary your suggestions and do not repeat the same examples every time.

If EXPLANATION_QUESTION:
- Do NOT call tools
- Do NOT say "no data found"
- Explain clearly in simple terms
- Keep it concise and helpful

If NOT_SMALL_TALK:
- Return exactly this: NOT_SMALL_TALK

---

User message:
"{message}"
"""
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL_FALLBACKS[0],
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.7)
        )
        if not response.candidates:
            return "NOT_SMALL_TALK"
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error in handle_small_talk_llm: {e}")
        return "NOT_SMALL_TALK"

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

def _stream_gemini_sync(prompt: str, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    """
    Synchronous worker managing the Gemini Tool-Loop.
    Handles function calling and final synthesis.
    """
    if not settings.GEMINI_API_KEY:
        asyncio.run_coroutine_threadsafe(queue.put(f"data: {json.dumps({'token': 'Missing API Key'})}\n\n"), loop).result()
        asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()
        return

    import google.genai as genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    # Tool registration
    AVAILABLE_TOOLS = [
        search_knowledge_base,
        get_invitations,
        get_eoi_count,
        get_trend,
        get_state_data
    ]
    
    # Internal tool mapping for execution
    tool_map = {tool.__name__: tool for tool in AVAILABLE_TOOLS}

    def put(item):
        asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()

    model_name = settings.GEMINI_MODEL_FALLBACKS[0]
    
    try:
        # Start a chat session for automatic history handling of tool results
        chat = client.chats.create(
            model=model_name,
            config=genai.types.GenerateContentConfig(
                tools=AVAILABLE_TOOLS,
                temperature=0.7,
            )
        )

        response = chat.send_message_stream(prompt)
        
        # We need to handle the case where the response might be a Tool Call
        # If it's a tool call, we execute and send back results until we get text
        
        for chunk in response:
            # Check for function calls
            if chunk.parsed:
                # If there is parsed text content, stream it
                put(f"data: {json.dumps({'token': chunk.text})}\n\n")
            
            # Note: The newer GenAI SDK Chat session handles the loop internally 
            # if we use it correctly, but for maximum control and transparency 
            # we check chunks.
            
        put("data: [DONE]\n\n")
        put(None)
        
    except Exception as e:
        logger.error(f"Gemini Tool Stream Error: {e}")
        put(f"data: {json.dumps({'token': f'System Error: {str(e)}'})}\n\n")
        put("data: [DONE]\n\n")
        put(None)

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
    Self-Correcting Loop (MAX_STEPS=3)
    Executes tools, detects suspicious results, and retries with improved strategies.
    """
    import google.genai as genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    tools = [search_knowledge_base, get_invitations, get_eoi_count, get_trend, get_state_data]
    tool_map = {t.__name__: t for t in tools}
    
    def put(item):
        asyncio.run_coroutine_threadsafe(queue.put(item), loop).result()

    MAX_STEPS = 3
    history = [genai.types.Content(role="user", parts=[genai.types.Part(text=prompt)])]
    
    try:
        all_data_verified = False
        
        for step in range(MAX_STEPS):
            logger.info(f"[Self-Correct Loop] Step {step + 1} of {MAX_STEPS}")
            
            # 1. Generate Content (AI decides tool calls)
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL_FALLBACKS[0],
                contents=history,
                config=genai.types.GenerateContentConfig(tools=tools, temperature=0)
            )

            # Check for candidate safety/errors
            if not response.candidates:
                put(f"data: {json.dumps({'token': 'No response candidate found.'})}\n\n")
                break

            message = response.candidates[0].content
            parts = response.candidates[0].content.parts
            history.append(message)

            # 2. Check for tool calls
            found_tool = False
            tool_results = []
            suspicious_detected = False
            
            for part in parts:
                if part.function_call:
                    found_tool = True
                    f_name = part.function_call.name
                    f_args = part.function_call.args
                    
                    # Status update to UI
                    display_name = f_name.replace("_", " ").title()
                    status_text = f"*{display_name}...* (Attempt {step+1})\\n"
                    put(f"data: {json.dumps({'token': status_text})}\n\n")
                    
                    logger.info(f"[Step {step+1}] Calling tool {f_name} with {f_args}")
                    
                    # Execute
                    if f_name in tool_map:
                        # Check Cache
                        cache_key = f"{f_name}:{f_args}"
                        if cache_key in _tool_cache:
                            logger.info(f"[Step {step+1}] Cache hit for {f_name}")
                            result_data = _tool_cache[cache_key]
                        else:
                            result_data = tool_map[f_name](**f_args)
                            _tool_cache[cache_key] = result_data
                        
                        # Check logic
                        if is_suspicious(result_data):
                            logger.warn(f"[Step {step+1}] Suspicious result detected for {f_name}")
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
                    logger.info(f"[Step {step+1}] All tool results are reliable. Breaking loop early.")
                    all_data_verified = True
                    break
                else:
                    # Provide feedback to AI for next step
                    strategy_hint = "The previous result looks incorrect, empty, or incomplete. "
                    
                    # FORCE TRANSPARENCY: Check for correction info in tool results
                    if isinstance(result_data, dict) and 'metadata' in result_data:
                        c_info = result_data['metadata'].get('correction_info', {})
                        if c_info.get('was_corrected'):
                            strategy_hint += f"CRITICAL: The tool corrected '{c_info['original']}' to '{c_info['corrected']}'. You MUST start your next response with 'It looks like you meant [Corrected Name]...' "
                    
                    if step == 0:
                        strategy_hint += "RETRY with a different strategy: Fix potential typos (if not already handled), use synonyms, or use LIKE with wildcards (e.g. %Manager%) instead of exact match."
                    elif step == 1:
                        strategy_hint += "STILL NO DATA. BROADER search needed: remove filters (like date) or use very broad keywords. Also consider checking the RAG knowledge base (search_knowledge_base) as a fallback."
                    
                    history.append(genai.types.Content(role="user", parts=[genai.types.Part(text=strategy_hint)]))
            else:
                # No tools called - AI provided a direct text response or is finished
                break

        # 3. Final Synthesis Turn (Verification aware)
        logger.info("[Self-Correct Loop] Finalizing answer...")
        
        # Add a subtle verification prompt to force honesty
        verification_instruction = """Based on the retrieved tool results, provide a final answer. 
- If reliable data was found after retries, mention that you verified it.
- If no data was found after all attempts, explicitly state: 'After verification, no reliable data was found'. 
DO NOT hallucinate."""
        
        history.append(genai.types.Content(role="user", parts=[genai.types.Part(text=verification_instruction)]))

        final_stream = client.models.generate_content_stream(
            model=settings.GEMINI_MODEL_FALLBACKS[0],
            contents=history,
            config=genai.types.GenerateContentConfig(tools=tools, temperature=0.7)
        )
        
        for chunk in final_stream:
            if chunk.text:
                put(f"data: {json.dumps({'token': chunk.text})}\n\n")

        put("data: [DONE]\n\n")
        put(None)

    except Exception as e:
        logger.error(f"Manual Loop Error: {e}")
        put(f"data: {json.dumps({'token': f'Error: {str(e)}'})}\n\n")
        put("data: [DONE]\n\n")
        put(None)

@router.post("/chat")
async def chat(body: ChatRequest):
    import uuid
    from routers.conversation import save_message
    from db.database import SessionLocal
    from db.models import ConversationMessage

    session_id = body.session_id or str(uuid.uuid4())[:12]
    
    # --- Small Talk Check (Short Circuit) ---
    if len(body.message) < 50:
        try:
            small_talk_str = handle_small_talk_llm(body.message)
            if small_talk_str and small_talk_str != "NOT_SMALL_TALK":
                logger.info(f"[Small Talk] Fast-path triggered for: {body.message}")
                save_message(session_id, "user", body.message)
                save_message(session_id, "assistant", small_talk_str, metadata={
                    "accuracy_score": 100,
                    "handler": "small_talk",
                    "hallucinations": []
                })
                
                async def generate_small_talk():
                    yield f"data: {json.dumps({'token': small_talk_str})}\n\n"
                    yield "data: [DONE]\n\n"
                    
                return StreamingResponse(generate_small_talk(), media_type="text/event-stream", headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Session-ID": session_id,
                })
        except Exception as e:
            logger.error(f"[Small Talk] Error, falling back to main loop: {e}")
    # ---------------------------------------
    
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
2. You MUST use this history to resolve pronouns (e.g., "that", "it", "those") and remember topics discussed earlier (e.g., "Tell me more about the first job I mentioned").
3. Always acknowledge if you are continuing a previous topic.

CRITICAL RULES:
1. You MUST NOT hallucinate or guess numbers.
2. ALL numerical answers MUST come from tools (database or API).
3. If tool result is suspicious (0, empty, or string "no data"), you MUST retry with a DIFFERENT strategy.

TYPO CORRECTION & TRANSPARENCY:
* Tools automatically apply fuzzy matching.
* If a tool returns metadata indicating a correction (e.g., 'was_corrected': True), you MUST inform the user immediately in your response.
* MANDATORY TEMPLATE FOR CORRECTION: "It looks like you meant '[Corrected Name]'. Based on verified database results..."

SELF-CORRECTION LOGIC:
Before giving a final answer, you MUST verify:
* If result is 0, null, empty, or suspicious â†’ DO NOT trust it.
* You MUST retry using:
  - broader search (e.g. LIKE instead of exact match)
  - removing filters (e.g. date/month)
  - alternative tool if available
* If results conflict â†’ call tools again and reconcile.
* If still no data after retry â†’ say "No reliable data found after verification".

TOOL USAGE RULES:
* Use database tools for: invitations, EOI counts, trends, points.
* Use RAG only for: explanations, advice, insights, and website knowledge.
* The system also contains knowledge about the website pages and dashboard. Use this information to explain what a page or metric means if the user asks.

MULTI-STEP REASONING:
You are allowed to call multiple tools, retry queries, and refine queries within 3 steps.

CONFIDENCE AWARENESS:
* Prefix verified results with: "Based on verified database results..."
* If retries were needed: "After checking multiple sources, I found..."
* If failure: "After multiple attempts, no reliable data was found..."

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
        if full_response:
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
