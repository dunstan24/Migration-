import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine
import logging
import csv
import re
from pathlib import Path
from rapidfuzz import process
from rag.chroma_client import get_or_create_collection, query_documents_with_scores, query_documents_by_category

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "warehouse.db"
CSV_PATH = Path(__file__).resolve().parent.parent / "occupation.csv"
RAG_RELEVANCE_THRESHOLD = 0.75

# Load all occupations once
ALL_OCCUPATIONS = []
try:
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            occ = row.get('Occupation', '')
            # Clean ANSI Code: e.g. "131112 Sales and Marketing Manager" -> "Sales and Marketing Manager"
            match = re.search(r'^\d{6}\s+(.*)$', occ)
            if match:
                ALL_OCCUPATIONS.append(match.group(1).strip())
            else:
                ALL_OCCUPATIONS.append(occ.strip())
    logger.info(f"Loaded {len(ALL_OCCUPATIONS)} occupations for fuzzy matching.")
except Exception as e:
    logger.error(f"Failed to load occupation list: {e}")

def correct_occupation(input_job: str):
    """
    Find the closest occupation match using rapidfuzz.
    Returns (corrected_job, score, was_corrected)
    """
    if not input_job or not ALL_OCCUPATIONS:
        return input_job, 0, False
        
    match, score, _ = process.extractOne(input_job, ALL_OCCUPATIONS)
    
    if score > 85: # Threshold for high confidence match
        return match, score, (match.lower() != input_job.lower())
    return input_job, score, False

def search_knowledge_base(query: str) -> str:
    """
    Search the RAG knowledge base for general information, context, explanations, career advice, and descriptions.
    Do NOT use this for exact counts or recent trends.
    """
    try:
        collection = get_or_create_collection("migration-docs")
        query_lower = query.lower()
        occupation_keywords = ['occupation', 'how many', 'list', 'all occupations', 'jobs', 'roles', 'professions']
        is_occupation_query = any(keyword in query_lower for keyword in occupation_keywords)
        
        if is_occupation_query:
            docs, _ = query_documents_by_category(collection, query, category='occupations', n_results=10)
            if docs:
                return "Knowledge Base Results:\n" + "\n".join(f"- {d}" for d in docs)
        
        docs, distances = query_documents_with_scores(collection, query, n_results=5)
        relevant = [doc for doc, dist in zip(docs, distances) if dist < 0.8]
        if relevant:
            return "Knowledge Base Results:\n" + "\n".join(f"- {d}" for d in relevant)
        return "No relevant insights found in the knowledge base."
    except Exception as e:
        logger.error(f"KB Search error: {e}")
        return f"Error searching knowledge base: {e}"

def get_invitations(occupation: str, months: int = 12) -> dict:
    """
    Get the exact number of invitations issued for a specific occupation over the last X months.
    """
    try:
        # Typo Correction
        corrected_job, score, was_corrected = correct_occupation(occupation)
        target_job = corrected_job
        
        conn = get_mysql_wrapper(settings)
        cur = conn.cursor()
        
        # 1. Try Strict Match
        cur.execute('''
            SELECT COALESCE(SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END), 0)
            FROM eoi_records 
            WHERE occupation_name = %s
            AND UPPER(eoi_status) = 'INVITED'
        ''', (target_job,))
        result = cur.fetchone()[0]
        query_type = "exact"
        
        # 2. Try LIKE Fallback if 0 (even after correction)
        if result == 0:
            cur.execute('''
                SELECT COALESCE(SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END), 0)
                FROM eoi_records 
                WHERE occupation_name LIKE %s
                AND UPPER(eoi_status) = 'INVITED'
            ''', (f"%{target_job}%",))
            result = cur.fetchone()[0]
            query_type = "like"
        
        conn.close()
        
        msg = f"Database result: There were approximately {result or 0} invitations for {target_job} on record."
        if result == 0:
            msg = f"No invitations found for '{target_job}' after searching."

        return {
            "result": msg,
            "metadata": {
                "query_type": query_type,
                "count": int(result or 0),
                "is_empty": (result == 0),
                "correction_info": {
                    "original": occupation,
                    "corrected": corrected_job,
                    "was_corrected": was_corrected,
                    "score": score
                }
            }
        }
    except Exception as e:
        logger.error(f"DB error: {e}")
        return {"result": f"Error retrieving invitations: {e}", "metadata": {"error": True}}

def get_eoi_count(occupation: str) -> dict:
    """
    Get the total number of submitted EOI (Expression of Interest) applications for an occupation.
    """
    try:
        corrected_job, score, was_corrected = correct_occupation(occupation)
        target_job = corrected_job

        conn = get_mysql_wrapper(settings)
        cur = conn.cursor()
        
        # Try exact first
        cur.execute('''
            SELECT COALESCE(SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END), 0),
                   AVG(points), MAX(points)
            FROM eoi_records 
            WHERE occupation_name = %s
            AND UPPER(eoi_status) = 'SUBMITTED'
        ''', (target_job,))
        total, avg_pts, max_pts = cur.fetchone()
        query_type = "exact"
        
        # Fallback to LIKE
        if not total:
            cur.execute('''
                SELECT COALESCE(SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END), 0),
                       AVG(points), MAX(points)
                FROM eoi_records 
                WHERE occupation_name LIKE %s
                AND UPPER(eoi_status) = 'SUBMITTED'
            ''', (f"%{target_job}%",))
            total, avg_pts, max_pts = cur.fetchone()
            query_type = "like"
            
        conn.close()
        
        if not total:
            return {
                "result": f"No submitted EOIs found for '{target_job}'.",
                "metadata": {
                    "query_type": query_type, 
                    "count": 0, 
                    "is_empty": True,
                    "correction_info": {"original": occupation, "corrected": corrected_job, "was_corrected": was_corrected, "score": score}
                }
            }
            
        msg = f"Database result: {int(total)} total submitted EOIs for {target_job}. Average points: {round(avg_pts or 0, 1)}, Maximum points: {max_pts}."
        return {
            "result": msg,
            "metadata": {
                "query_type": query_type, 
                "count": int(total), 
                "is_empty": False,
                "correction_info": {"original": occupation, "corrected": corrected_job, "was_corrected": was_corrected, "score": score}
            }
        }
    except Exception as e:
        logger.error(f"DB error: {e}")
        return {"result": f"Error retrieving EOI count: {e}", "metadata": {"error": True}}

def get_trend(occupation: str, metric: str) -> dict:
    """
    Check the trend (increase/decrease) for an occupation. 
    Metric: 'eoi' or 'ads'
    """
    try:
        corrected_job, score, was_corrected = correct_occupation(occupation)
        target_job = corrected_job

        conn = get_mysql_wrapper(settings)
        cur = conn.cursor()
        
        results = []
        query_type = "exact"
        
        if metric == 'ads':
            # Exact match attempt
            cur.execute('SELECT 1 FROM jsa_monthly_ads WHERE anzsco_name = %s LIMIT 1', (target_job,))
            if not cur.fetchone():
                query_type = "like"
                match_pattern = f"%{target_job}%"
            else:
                match_pattern = target_job

            cur.execute('''
                SELECT as_at_month_no, as_at_year, SUM(job_ads_count)
                FROM jsa_monthly_ads
                WHERE anzsco_name LIKE %s
                GROUP BY as_at_year, as_at_month_no
                ORDER BY as_at_year DESC, as_at_month_no DESC
                LIMIT 5
            ''', (match_pattern,))
            results = cur.fetchall()
        else:
            # EOI trend
            cur.execute('SELECT 1 FROM eoi_records WHERE occupation_name = %s LIMIT 1', (target_job,))
            if not cur.fetchone():
                query_type = "like"
                match_pattern = f"%{target_job}%"
            else:
                match_pattern = target_job

            cur.execute('''
                SELECT as_at_year, as_at_month_no, SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END)
                FROM eoi_records
                WHERE occupation_name LIKE %s AND UPPER(eoi_status)='SUBMITTED'
                GROUP BY as_at_year, as_at_month_no
                ORDER BY as_at_year DESC, as_at_month_no DESC
                LIMIT 5
            ''', (match_pattern,))
            results = cur.fetchall()
            
        conn.close()
        
        if not results:
            if metric == 'ads':
                return {"result": f"No job advertisement data available for '{target_job}'. This metric may not be tracked in the system or no ads have been posted for this occupation.", 
                        "metadata": {"query_type": query_type, "count": 0, "is_empty": True, "metric": "ads", "data_unavailable": True, "correction_info": {"was_corrected": was_corrected, "corrected": corrected_job, "original": occupation}}}
            return {"result": f"No trend data for '{target_job}'.", "metadata": {"query_type": query_type, "count": 0, "is_empty": True, "correction_info": {"was_corrected": was_corrected, "corrected": corrected_job, "original": occupation}}}
        
        # Format dates clearly: convert month_no to month name
        month_names = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
                      7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
        
        if metric == 'ads':
            # For ads: results are (month_no, year, count)
            formatted = [f"{month_names.get(r[0], f'Month {r[0]}')} {r[1]}: {r[2]} ads" for r in results]
        else:
            # For EOI: results are (year, month_no, count)
            formatted = [f"{month_names.get(r[1], f'Month {r[1]}')} {r[0]}: {r[2]} EOIs" for r in results]
        
        txt = " → ".join(formatted)
        date_range = f"from {formatted[-1].split(':')[0]} to {formatted[0].split(':')[0]}"  # oldest to newest
        
        return {
            "result": f"Database trend for {target_job} ({date_range}): {txt}",
            "metadata": {
                "query_type": query_type, 
                "count": len(results), 
                "is_empty": False,
                "metric": metric,
                "date_range": date_range,
                "correction_info": {"was_corrected": was_corrected, "corrected": corrected_job, "original": occupation}
            }
        }
    except Exception as e:
        logger.error(f"DB error: {e}")
        return {"result": f"Error retrieving trend: {e}", "metadata": {"error": True}}

def get_state_data(occupation: str) -> dict:
    """
    Get the state-by-state data (shortages and allocations) for an occupation.
    """
    try:
        corrected_job, score, was_corrected = correct_occupation(occupation)
        target_job = corrected_job

        conn = get_mysql_wrapper(settings)
        cur = conn.cursor()
        
        cur.execute('SELECT 1 FROM osl_shortage WHERE occupation_name = %s LIMIT 1', (target_job,))
        if not cur.fetchone():
            query_type = "like"
            pattern = f"%{target_job}%"
        else:
            query_type = "exact"
            pattern = target_job

        cur.execute('''
            SELECT nsw, vic, qld, sa, wa, tas, nt, act 
            FROM osl_shortage 
            WHERE occupation_name LIKE %s
            ORDER BY year DESC LIMIT 1
        ''', (pattern,))
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return {"result": f"No state shortage data for '{target_job}'.", "metadata": {"query_type": query_type, "count": 0, "is_empty": True, "correction_info": {"was_corrected": was_corrected, "corrected": corrected_job, "original": occupation}}}
            
        states = ['NSW', 'VIC', 'QLD', 'SA', 'WA', 'TAS', 'NT', 'ACT']
        shortages = [states[i] for i, val in enumerate(row) if val]
        
        msg = f"Database result: {target_job} has critical shortages in: {', '.join(shortages)}." if shortages else f"{target_job} has no formal recorded state shortages."
        return {
            "result": msg,
            "metadata": {
                "query_type": query_type, 
                "count": len(shortages), 
                "is_empty": False,
                "correction_info": {"was_corrected": was_corrected, "corrected": corrected_job, "original": occupation}
            }
        }
    except Exception as e:
        logger.error(f"DB error: {e}")
        return {"result": f"Error retrieving state data: {e}", "metadata": {"error": True}}
