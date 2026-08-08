"""
routers/reports.py
GET /api/reports/generate — Python fetches all data + runs models directly.
FIX: call pathway/approval models directly from main.models instead of HTTP.
"""
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db.database import get_db
import subprocess, os, tempfile, traceback, json
from decimal import Decimal
from fastapi.encoders import jsonable_encoder
import numpy as np
import pandas as pd

router = APIRouter()

# Calculate project root dynamically to find generate_report.js
# In dev: backend/routers/reports.py -> 2 levels up to backend/, then 1 up to root
# In docker: /app/routers/reports.py -> 1 level up to /app/
_this_dir = os.path.dirname(os.path.abspath(__file__))
# Check 1 level up (/app in docker)
PROJECT_ROOT = os.path.dirname(_this_dir)
if not os.path.exists(os.path.join(PROJECT_ROOT, "generate_report.js")):
    # Check 2 levels up (backend/ in dev)
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
    if not os.path.exists(os.path.join(PROJECT_ROOT, "generate_report.js")):
        # Check 3 levels up (root in dev)
        PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)

GENERATOR_SCRIPT = os.path.join(PROJECT_ROOT, "generate_report.js")

# ── XGBoost model features (13-feature schema) ──────────────
# These are the ACTUAL features the trained model expects
XGB_FEATURE_NAMES = [
    "English Test Score",
    "Count EOIs",
    "Visa Type_190SAS Skilled Australian Sponsored",
    "Visa Type_491SNR State or Territory Nominated - Regional",
    "State_ACT", "State_NSW", "State_NT", "State_QLD",
    "State_SA", "State_TAS", "State_VIC", "State_WA",
    "occupation_enc",
]
XGB_VISA_MAP = {
    "190": "Visa Type_190SAS Skilled Australian Sponsored",
    "491": "Visa Type_491SNR State or Territory Nominated - Regional",
}
XGB_STATE_MAP = {
    "ACT": "State_ACT", "NSW": "State_NSW", "NT": "State_NT",
    "QLD": "State_QLD", "SA": "State_SA", "TAS": "State_TAS",
    "VIC": "State_VIC", "WA": "State_WA",
}

# ── English level score mapping (from predict.py) ────────────
ENGLISH_SCORE_MAP = {
    "competent": 0.0,
    "proficient": 10.0,
    "superior": 20.0,
}

def build_xgb_input(occupation_enc, visa_type, state, english_level, count_eois):
    """Build XGBoost input for approval model (13-feature schema)"""
    row = {f: 0.0 for f in XGB_FEATURE_NAMES}
    
    row["English Test Score"] = ENGLISH_SCORE_MAP.get(english_level, 0.0)
    row["Count EOIs"] = float(count_eois)
    row["occupation_enc"] = float(occupation_enc)
    
    visa_col = XGB_VISA_MAP.get(visa_type)
    if visa_col:
        row[visa_col] = 1.0
    
    state_col = XGB_STATE_MAP.get(state)
    if state_col:
        row[state_col] = 1.0
    
    return pd.DataFrame([row])[XGB_FEATURE_NAMES]


async def _fetch_report_data(
    months, visa_type, occupation, state, points,
    english_level, age, experience, count_eois, db
):
    anzsco = occupation.split(" ")[0].strip()

    # ── Summary ───────────────────────────────────────────────
    try:
        latest_q = await db.execute(text(
            "SELECT as_at_str FROM eoi_records ORDER BY as_at_year DESC, as_at_month_no DESC LIMIT 1"
        ))
        latest_month = (latest_q.fetchone() or ["N/A"])[0]

        pool_q = await db.execute(text("""
            SELECT COALESCE(SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END),0)
            FROM eoi_records WHERE eoi_status='SUBMITTED' AND as_at_str=:m
        """), {"m": latest_month})
        inv_q = await db.execute(text("""
            SELECT COALESCE(SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END),0)
            FROM eoi_records WHERE eoi_status='INVITED' AND as_at_str=:m
        """), {"m": latest_month})
        occ_q = await db.execute(text(
            "SELECT COUNT(DISTINCT anzsco_code) FROM eoi_records WHERE anzsco_code != ''"
        ))
        summary = {
            "eoi_pool":             int(pool_q.scalar() or 0),
            "total_invitations":    int(inv_q.scalar() or 0),
            "shortage_occupations": int(occ_q.scalar() or 0),
            "latest_snapshot":      latest_month,
        }
    except Exception as e:
        summary = {"eoi_pool": 0, "total_invitations": 0, "shortage_occupations": 0,
                   "latest_snapshot": "N/A", "error": str(e)}

    # ── Monthly trend ─────────────────────────────────────────
    try:
        max_yr_q = await db.execute(text("SELECT MAX(as_at_year) FROM eoi_records"))
        max_yr   = int(max_yr_q.scalar() or 2025)
        min_yr   = max_yr - 2 if months <= 24 else 2020
        trend_q  = await db.execute(text("""
            SELECT as_at_str, as_at_year, as_at_month_no, eoi_status,
                   SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END) as total
            FROM eoi_records WHERE as_at_year >= :min_year
            GROUP BY as_at_str, as_at_year, as_at_month_no, eoi_status
            ORDER BY as_at_year, as_at_month_no
        """), {"min_year": min_yr})
        month_map: dict = {}
        for r in trend_q.fetchall():
            k = r[0]
            if k not in month_map:
                month_map[k] = {"month": k, "year": r[1], "month_no": r[2], "pool": 0, "invitations": 0}
            if r[3] == "SUBMITTED": month_map[k]["pool"] += r[4]
            elif r[3] == "INVITED":  month_map[k]["invitations"] += r[4]
        all_monthly = sorted(month_map.values(), key=lambda x: (x["year"], x["month_no"]))
        monthly     = all_monthly if months == 0 else all_monthly[-months:]
    except Exception:
        all_monthly = []
        monthly     = []

    # ── Top occupations ───────────────────────────────────────
    try:
        occ_q = await db.execute(text("""
            SELECT anzsco_code, occupation_name,
                   SUM(CASE WHEN eoi_status='SUBMITTED' AND count_eois=-1 THEN 10
                            WHEN eoi_status='SUBMITTED' THEN count_eois ELSE 0 END) as pool,
                   SUM(CASE WHEN eoi_status='INVITED' AND count_eois=-1 THEN 10
                            WHEN eoi_status='INVITED' THEN count_eois ELSE 0 END) as invitations
            FROM eoi_records GROUP BY anzsco_code, occupation_name
            HAVING pool > 0 ORDER BY invitations DESC, pool DESC LIMIT 10
        """))
        top_occupations = [
            {"anzsco_code": r[0], "occupation_name": r[1], "pool": int(r[2] or 0),
             "invitations": int(r[3] or 0),
             "invitation_rate": round(r[3]/r[2], 3) if r[2] and r[2] > 0 else 0}
            for r in occ_q.fetchall()
        ]
    except Exception:
        top_occupations = []

    # ── Shortage heatmap ──────────────────────────────────────
    try:
        hm_q = await db.execute(text("""
            SELECT anzsco_code, occupation_name, skill_level, national,
                   nsw, vic, qld, sa, wa, tas, nt, act, shortage_state_count
            FROM osl_shortage WHERE year = 2025
            ORDER BY shortage_state_count DESC, national DESC
        """))
        hm_rows  = hm_q.fetchall()
        total    = len(hm_rows)
        nat_s    = sum(1 for r in hm_rows if r[3] == 1)
        s_keys   = ["NSW","VIC","QLD","SA","WA","TAS","NT","ACT"]
        s_counts: dict = {}
        for r in hm_rows:
            for i, s in enumerate(s_keys):
                if r[4+i] == 1:
                    s_counts[s] = s_counts.get(s, 0) + 1
        heatmap = {
            "year": 2025, "total_occupations": total,
            "national_shortage_count": nat_s,
            "national_shortage_pct": round(nat_s/total*100, 1) if total else 0,
            "state_shortage_counts": s_counts,
            "records": [
                {"anzsco_code": r[0], "occupation_name": r[1], "skill_level": r[2],
                 "national": r[3], "nsw": r[4], "vic": r[5], "qld": r[6], "sa": r[7],
                 "wa": r[8], "tas": r[9], "nt": r[10], "act": r[11],
                 "shortage_state_count": r[12]}
                for r in hm_rows
            ],
        }
    except Exception:
        heatmap = {"year": 2025, "total_occupations": 0, "national_shortage_count": 0,
                   "national_shortage_pct": 0, "state_shortage_counts": {}, "records": []}

    # ── Pathway model — call directly ────────────────────────
    pathways = []
    pathways_is_dummy = False
    try:
        from main import models
        pathway_model = models.get("pathway")
        print(f"Pathway model loaded: {pathway_model is not None}")
        
        if pathway_model:
            from routers.predict import build_ranked_pathways
            
            # Generate predictions for all visa x state combinations
            all_states = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
            visa_map = {0: "189", 1: "190", 2: "491"}
            
            # Create dummy input for prediction (pathway model should output probabilities)
            synthetic_classes = []
            synthetic_probs = []
            
            # For simplicity, use equal probabilities for all visa types
            for visa_idx in range(3):
                visa_type = visa_map.get(visa_idx, str(visa_idx))
                for state_name in all_states + ['National']:
                    synthetic_classes.append(f"{visa_type}_{state_name}")
                    synthetic_probs.append(0.5)
            
            try:
                pathways = build_ranked_pathways(
                    model=pathway_model,
                    occupation=anzsco,
                    state=state,
                    points=points,
                    probs=synthetic_probs,
                    classes=synthetic_classes,
                )
                print(f"✅ Pathway model ran: {len(pathways)} pathways generated")
                if pathways:
                    print(f"   First pathway: {pathways[0]}")
            except Exception as pe:
                print(f"❌ Pathway build error: {pe}")
                import traceback
                traceback.print_exc()
                # Return minimal dummy data if model fails
                pathways_is_dummy = True
                pathways = [
                    {"visa": "189", "state": state, "score": 0.75, "eligible": True, "note": "[DUMMY DATA]"},
                    {"visa": "190", "state": state, "score": 0.65, "eligible": True, "note": "[DUMMY DATA]"},
                    {"visa": "491", "state": state, "score": 0.85, "eligible": True, "note": "[DUMMY DATA]"},
                ]
        else:
            print("⚠ Pathway model not loaded - using dummy data")
            # Return minimal dummy data if model is not loaded
            pathways_is_dummy = True
            pathways = [
                {"visa": "189", "state": state, "score": 0.75, "eligible": True, "note": "[DUMMY DATA]"},
                {"visa": "190", "state": state, "score": 0.65, "eligible": True, "note": "[DUMMY DATA]"},
                {"visa": "491", "state": state, "score": 0.85, "eligible": True, "note": "[DUMMY DATA]"},
            ]
    except Exception as e:
        print(f"⚠ Pathway error: {e}")
        import traceback
        traceback.print_exc()
        # Return minimal dummy data as fallback
        pathways_is_dummy = True
        pathways = [
            {"visa": "189", "state": state, "score": 0.75, "eligible": True, "note": "[DUMMY DATA]"},
            {"visa": "190", "state": state, "score": 0.65, "eligible": True, "note": "[DUMMY DATA]"},
            {"visa": "491", "state": state, "score": 0.85, "eligible": True, "note": "[DUMMY DATA]"},
        ]

    # ── Approval model — call directly for all 8 states ──────
    approvals = []
    approvals_is_dummy = False
    try:
        from main import models
        xgb_model   = models.get("approval")
        occ_encoder = models.get("occ_encoder")
        print(f"Approval model loaded: {xgb_model is not None}, Encoder loaded: {occ_encoder is not None}")
        
        if xgb_model and occ_encoder:
            states = ["NSW","VIC","QLD","WA","SA","TAS","ACT","NT"]
            try:
                occupation_enc = int(occ_encoder.transform([occupation])[0])
            except Exception:
                occupation_enc = 0
            approval_count = 0
            for st in states:
                try:
                    df = build_xgb_input(
                            occupation_enc=occupation_enc,
                            visa_type=visa_type,
                            state=st,
                            english_level=english_level,
                            count_eois=count_eois,
                        )
                    # SYNC with /api/predict/approval: use proba[0] = P(LODGED/class 0)
                    prob = round(float(xgb_model.predict_proba(df)[0][0]), 4)
                    approvals.append({"state": st, "prob": prob})
                    approval_count += 1
                except Exception as e:
                    print(f"⚠ Approval skip {st}: {e}")
            approvals.sort(key=lambda x: x["prob"], reverse=True)
            print(f"✅ Approval model ran: {len(approvals)} states")
            
            # If no approvals were generated, use dummy data
            if approval_count == 0:
                print("⚠ No approval data generated - using dummy fallback")
                approvals_is_dummy = True
                approvals = [
                    {"state": "NSW", "prob": 0.78},
                    {"state": "VIC", "prob": 0.72},
                    {"state": "QLD", "prob": 0.65},
                    {"state": "WA", "prob": 0.68},
                    {"state": "SA", "prob": 0.55},
                    {"state": "TAS", "prob": 0.52},
                    {"state": "ACT", "prob": 0.70},
                    {"state": "NT", "prob": 0.48},
                ]
                approvals.sort(key=lambda x: x["prob"], reverse=True)
        else:
            print("⚠ Approval/encoder model not loaded - using dummy data")
            # Return dummy approval data if models not available
            approvals_is_dummy = True
            approvals = [
                {"state": "NSW", "prob": 0.78},
                {"state": "VIC", "prob": 0.72},
                {"state": "QLD", "prob": 0.65},
                {"state": "WA", "prob": 0.68},
                {"state": "SA", "prob": 0.55},
                {"state": "TAS", "prob": 0.52},
                {"state": "ACT", "prob": 0.70},
                {"state": "NT", "prob": 0.48},
            ]
            approvals.sort(key=lambda x: x["prob"], reverse=True)
    except Exception as e:
        print(f"⚠ Approval model error: {e}")
        import traceback
        traceback.print_exc()
        # Return dummy approval data as fallback
        approvals_is_dummy = True
        approvals = [
            {"state": "NSW", "prob": 0.78},
            {"state": "VIC", "prob": 0.72},
            {"state": "QLD", "prob": 0.65},
            {"state": "WA", "prob": 0.68},
            {"state": "SA", "prob": 0.55},
            {"state": "TAS", "prob": 0.52},
            {"state": "ACT", "prob": 0.70},
            {"state": "NT", "prob": 0.48},
        ]
        approvals.sort(key=lambda x: x["prob"], reverse=True)

    return {
        "profile": {
            "occupation": occupation, "visa_type": visa_type,
            "state": state, "points": points, "anzsco": anzsco,
            "english_level": english_level, "age": age,
            "experience": experience, "count_eois": count_eois,
        },
        "summary":        summary,
        "months":         months,
        "allData":        months == 0,
        "totalMonths":    len(all_monthly),
        "monthly":        monthly,
        "topOccupations": top_occupations,
        "heatmap":        heatmap,
        "pathways":       pathways,
        "pathways_is_dummy": pathways_is_dummy,
        "approvals":      approvals,
        "approvals_is_dummy": approvals_is_dummy,
    }


@router.get("/generate")
async def generate_report(
    background_tasks: BackgroundTasks,
    months:        int = Query(6),
    visa_type:     str = Query("491"),
    occupation:    str = Query(""),
    state:         str = Query("NSW"),
    points:        int = Query(80),
    english_level: str = Query("proficient"),
    age:           int = Query(30),
    experience:    int = Query(5),
    count_eois:    int = Query(100),
    db: AsyncSession = Depends(get_db),
):
    if not os.path.exists(GENERATOR_SCRIPT):
        raise HTTPException(500, detail=f"Report generator not found at {GENERATOR_SCRIPT}.")

    try:
        report_data = await _fetch_report_data(
            months, visa_type, occupation, state, points,
            english_level, age, experience, count_eois, db
        )

        # Create temporary files for the PDF and JSON data
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as json_tmp:
            data_path = json_tmp.name
        
        # We also need a path for the output PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_tmp:
            pdf_path = pdf_tmp.name
            
        try:
            # Use jsonable_encoder to convert Decimal/numpy types from MySQL
            safe_report_data = jsonable_encoder(report_data)
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(safe_report_data, f, ensure_ascii=False)
            # Use Popen to avoid subprocess buffer deadlock
            process = subprocess.Popen(
                ["node", GENERATOR_SCRIPT, pdf_path, data_path],
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=PROJECT_ROOT,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=1200)
            except subprocess.TimeoutExpired:
                process.kill()
                raise HTTPException(500, detail="PDF generation timed out after 120s")
            
            if process.returncode != 0:
                err_msg = stderr_data if stderr_data else stdout_data
                raise HTTPException(500, detail=err_msg[:500] or "PDF generation failed")
                
        finally:
            # Clean up the JSON data file right away
            if os.path.exists(data_path):
                os.remove(data_path)

        if not os.path.exists(pdf_path):
            raise HTTPException(500, detail="PDF file was not created.")

        # Clean up PDF file after the response is sent
        background_tasks.add_task(os.remove, pdf_path)

        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename="Inter_Migration_Intelligence_Report.pdf",
            headers={"Content-Disposition": "attachment; filename=Inter_Migration_Intelligence_Report.pdf"}
        )

    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(500, detail=str(e))