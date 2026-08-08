"""
routers/predict.py

POST /api/predict/pathway   — GBM model_a.joblib      (visa subclass recommender)
  Input: occupation (ANZSCO), state, points
  (english_level / age / experience are already encoded within the points score)

POST /api/predict/approval  — XGBoost model_xgboost.json  (EOI approval probability)
  Input: visa_type, occupation, state, english_level, count_eois
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Tuple
import numpy as np
import pandas as pd
import math
import traceback
import json
from functools import lru_cache

from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine
import os
from config import settings


router = APIRouter()

# ── Load State Requirements ───────────────────────────────────
REQUIREMENTS_DB = {}
try:
    req_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw", "requirement_state", "requirements_all_states.json")
    if os.path.exists(req_path):
        with open(req_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                state = item.get("state code", "")
                stream = str(item.get("state stream", "")).replace("subclass_", "")
                key = f"{stream}_{state}"
                REQUIREMENTS_DB[key] = {
                    "requirements": item.get("requirements", ""),
                    "service_fee": item.get("service fee", "")
                }
except Exception as e:
    print(f"Error loading requirements DB: {e}")

# ── Load Occupations from CSV ────────────────────────────────
OCCUPATIONS_LIST = []
try:
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "occupation.csv")
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "occupation.csv")
    if os.path.exists(csv_path):
        df_occ = pd.read_csv(csv_path)
        if "Occupation" in df_occ.columns:
            OCCUPATIONS_LIST = df_occ["Occupation"].dropna().tolist()
            print(f"Loaded {len(OCCUPATIONS_LIST)} occupations from CSV")
    else:
        print(f"CSV not found at {csv_path}")
except Exception as e:
    print(f"Error loading occupations CSV: {e}")

DF_RAW_EOI = None
try:
    eoi_csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "df_raw.csv")
    if os.path.exists(eoi_csv_path):
        DF_RAW_EOI = pd.read_csv(eoi_csv_path)
        print(f"Loaded {len(DF_RAW_EOI)} rows from df_raw.csv")
    else:
        print(f"CSV not found at {eoi_csv_path}")
except Exception as e:
    print(f"Error loading raw EOI CSV: {e}")

# ── GBM pathway constants ─────────────────────────────────────
ALL_STATES   = ["NSW","VIC","QLD","WA","SA","TAS","ACT","NT"]
REGIONAL_STT = ["QLD","WA","SA","TAS","ACT","NT"]
VISAS = {0:"189 — Independent", 1:"190 — State Nominated", 2:"491 — Regional Sponsored"}

# ── New XGBoost feature schema (14 features) ─────────────────
XGB_FEATURE_NAMES = [
    "Count EOIs",
    "English Test Score",
    "Visa Type_189PTS Points-Tested Stream",
    "Visa Type_190SAS Skilled Australian Sponsored",
    "Visa Type_491SNR State or Territory Nominated - Regional",
    "State_ACT", "State_NSW", "State_NT", "State_QLD",
    "State_SA",  "State_TAS", "State_VIC", "State_WA",
    "occupation_enc",
]

VISA_COL_MAP = {
    "189": "Visa Type_189PTS Points-Tested Stream",
    "190": "Visa Type_190SAS Skilled Australian Sponsored",
    "491": "Visa Type_491SNR State or Territory Nominated - Regional",
}

STATE_COL_MAP = {
    "ACT": "State_ACT", "NSW": "State_NSW", "NT": "State_NT",
    "QLD": "State_QLD", "SA":  "State_SA",  "TAS": "State_TAS",
    "VIC": "State_VIC", "WA":  "State_WA",
}

ENGLISH_SCORE_MAP = {
    "competent":  0.0,
    "proficient": 10.0,
    "superior":   20.0,
}

# ── Count EOIs lookup from warehouse.db ──────────────────────
def lookup_count_eois(occupation: str, state: str, visa_type: str) -> Tuple[int, str]:
    """
    Auto-lookup Count EOIs from warehouse.db for the given combination.
    Returns (count, source) where source is:
      'warehouse_db'     — found in DB
      'fallback_default' — combination not in DB, using 50 as default
    """
    VISA_DB_MAP = {
        "189": "189PTS Points-Tested Stream",
        "190": "190SAS Skilled Australian Sponsored",
        "491": "491SNR State or Territory Nominated - Regional",
    }
    visa_full = VISA_DB_MAP.get(visa_type, visa_type)

    try:
        conn = get_mysql_wrapper(settings)
        # Get latest snapshot month first
        latest = conn.execute(
            "SELECT as_at_str FROM eoi_records ORDER BY as_at_year DESC, as_at_month_no DESC LIMIT 1"
        ).fetchone()

        if not latest:
            conn.close()
            return 50, "fallback_default"

        snapshot = latest[0]

        # Look up count for this exact combination in the latest snapshot
        row = conn.execute("""
            SELECT COALESCE(SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END), 0)
            FROM eoi_records
            WHERE as_at_str = %s
              AND occupation LIKE %s
              AND nominated_state = %s
              AND visa_type LIKE %s
              AND eoi_status = 'SUBMITTED'
        """, (snapshot, f"%{occupation.split()[0]}%", state, f"%{visa_type}%")).fetchone()

        conn.close()

        if row and row[0] and row[0] > 0:
            return int(row[0]), "warehouse_db"

        # Try broader search without state
        conn = get_mysql_wrapper(settings)
        row2 = conn.execute("""
            SELECT COALESCE(SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END), 0)
            FROM eoi_records
            WHERE as_at_str = %s
              AND occupation LIKE %s
              AND eoi_status = 'SUBMITTED'
        """, (snapshot, f"%{occupation.split()[0]}%")).fetchone()
        conn.close()

        if row2 and row2[0] and row2[0] > 0:
            return max(1, int(row2[0]) // 8), "warehouse_db"

    except Exception as e:
        print(f"Count EOIs lookup error: {e}")

    return 50, "fallback_default"


# ── Build XGBoost input ───────────────────────────────────────
def build_xgb_input(
    occupation_enc: int,
    visa_type: str,
    state: str,
    english_level: str,
    count_eois: int,
) -> pd.DataFrame:
    row = {f: 0.0 for f in XGB_FEATURE_NAMES}

    row["English Test Score"] = int(ENGLISH_SCORE_MAP.get(english_level, 0))
    row["Count EOIs"]         = int(count_eois)
    row["occupation_enc"]     = int(occupation_enc)

    visa_col = VISA_COL_MAP.get(visa_type)
    if visa_col:
        row[visa_col] = 1

    state_col = STATE_COL_MAP.get(state)
    if state_col:
        row[state_col] = 1

    # Ensure all values are int to match model json expectations
    row = {k: int(v) for k, v in row.items()}

    return pd.DataFrame([row])[XGB_FEATURE_NAMES]


# ── Logit-space probability helpers ──────────────────────────
def _logit(p: float) -> float:
    return math.log(max(p, 0.001) / max(1 - p, 0.001))

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))

def adjust_prob(base_prob: float, logit_adjustment: float) -> float:
    return round(_sigmoid(_logit(base_prob) + logit_adjustment), 4)


# ── GBM helpers ───────────────────────────────────────────────
def compute_shap(model):
    try:
        importances = model.named_steps["model"].feature_importances_
        pre = model.named_steps["preprocessor"]
        all_feats = list(pre.transformers_[0][2]) + list(pre.transformers_[1][2])
        total = importances.sum() or 1.0
        shap = {f: round(float(v / total), 4) for f, v in zip(all_feats, importances)}
        return dict(sorted(shap.items(), key=lambda x: x[1], reverse=True))
    except Exception:
        return {}


# ── Pathway scoring helpers ───────────────────────────────────
def get_shortage_adjustment(occupation: str, state: str, conn: SqliteToMysqlWrapper = None) -> float:
    """
    Get shortage adjustment. If conn is provided, it uses it (faster).
    Otherwise opens its own connection (slower).
    """
    adj = 0.0
    close_at_end = False
    try:
        if not conn:
            conn = get_mysql_wrapper(settings)
            close_at_end = True
            
        osl = conn.execute(
            f"SELECT national, [{state.lower()}] FROM osl_shortage WHERE anzsco_code=%s ORDER BY year DESC LIMIT 1",
            (occupation,)
        ).fetchone()
        if osl:
            if osl[1] == 1:   adj += 0.30
            elif osl[0] == 1: adj += 0.10
        forecast = conn.execute(
            "SELECT prob_2026 FROM shortage_forecast WHERE anzsco_code=%s AND state=%s LIMIT 1",
            (occupation, state)
        ).fetchone()
        if forecast:
            adj += float(forecast[0]) * 0.20
    except Exception:
        pass
    finally:
        if close_at_end and conn:
            conn.close()
    return adj

def get_quota_adjustment(state: str, visa: str, conn: SqliteToMysqlWrapper = None) -> float:
    try:
        close_at_end = False
        if not conn:
            conn = get_mysql_wrapper(settings)
            close_at_end = True
            
        q = conn.execute(
            "SELECT quota_amount FROM state_nomination_quotas WHERE state=%s AND visa_type LIKE %s LIMIT 1",
            (state, f"%{visa}%")
        ).fetchone()
        if q and q[0]:
            res = min(float(q[0]) / 5000.0 * 0.15, 0.15)
            if close_at_end: conn.close()
            return res
        if close_at_end: conn.close()
    except Exception:
        pass
    return 0.0

def get_skill_boost(points: int) -> float:
    """
    Points-only skill boost.
    English level, age, and work experience are already encoded within the
    Australian points test score — no separate adjustment needed.
    Returns a value in [0, 1] scaled to the realistic points range (65–140).
    """
    # Normalise against max realistic points ceiling
    return min(points / 120.0, 1.0)


# ── Ranked (visa × state) output ─────────────────────────────────────────────
def safe_get_proba(model, df, class_idx: int) -> float:
    """Safely get probability for a class index, even if missing from model."""
    try:
        probs = model.predict_proba(df)[0]
        classes = list(model.classes_)
        if class_idx in classes:
            return float(probs[classes.index(class_idx)])
    except Exception:
        pass
    return 0.0

def build_ranked_pathways(model, occupation: str, state: str,
                           points: int,
                           probs: list, classes: list) -> List[Dict]:
    """
    Builds the ranked list directly from the Multi-Class output (Visa_State).
    Points already encodes english/age/experience — boost is points-only.
    """
    physical_points = points
    skill_boost = get_skill_boost(physical_points)
    
    squash = True
    if physical_points >= 100:
        model_w, skill_w = 0.10, 0.90
    elif physical_points >= 85:
        model_w, skill_w = 0.30, 0.70
    else:
        model_w, skill_w = 0.40, 0.60

    def damp(p):
        if squash:
            factor = 0.2 if physical_points >= 100 else 0.3
            return 0.5 + (p - 0.5) * factor
        return p

    ranked = []
    
    # Pre-open connection for the loop performance boost
    conn = None
    try:
        conn = get_mysql_wrapper(settings)
    except Exception:
        pass

    for i, class_name in enumerate(classes):
        parts = str(class_name).split('_')
        if len(parts) != 2: continue
        visa_type, state_nm = parts[0], parts[1]
        
        # FILTER: Only show predictions for the user's selected state or National
        if state_nm != state and state_nm != 'National':
            continue
            
        p_val = float(probs[i])
        
        eligible = True
        if physical_points < 65 and visa_type in ['189', '190']: eligible = False
        if physical_points < 50 and visa_type == '491': eligible = False
        # Note: english / age / experience eligibility encoded within points
        
        state_match_bonus = 0.05 if state_nm == state else 0.0
        shortage = get_shortage_adjustment(occupation, state_nm, conn) if state_nm != 'National' else 0.0
        quota = get_quota_adjustment(state_nm, visa_type, conn) if state_nm != 'National' else 0.0
        
        score = (damp(p_val) * model_w) + (skill_boost * skill_w) + state_match_bonus + shortage + quota
        if visa_type == '491': score += 0.1
        
        req_data = REQUIREMENTS_DB.get(f"{visa_type}_{state_nm}", {})
        raw_req_text = req_data.get("requirements", "")
        req_fee = req_data.get("service_fee", "")
        
        # Clean the requirements text into readable paragraphs (No truncation)
        req_list = [p.strip() for p in raw_req_text.split('\n') if p.strip()]
            
        req_text_clean = "\n\n".join(req_list)
        
        # Create a concise note for quick preview
        note_text = req_list[0] if req_list else "No specific requirements loaded."
        if len(note_text) > 130:
            note_text = note_text[:127] + "..."
            
        visa_name = f"{visa_type} — "
        if visa_type == '189': visa_name += "Skilled Independent"
        elif visa_type == '190': visa_name += "Skilled Nominated"
        else: visa_name += "Skilled Work Regional (Provisional)"
        
        score_val = round(min(max(score, 0.0), 1.0), 4)

        ranked.append({
            "visa":      visa_type,
            "visa_name": visa_name,
            "state":     state_nm if state_nm not in ['National', 'ALL STATES'] else "Any (National/All States)",
            "score":     score_val if eligible else 0.0,
            "raw_score": score_val,
            "eligible":   eligible,
            "note":       note_text,
            "requirements": req_text_clean,
            "service_fee": req_fee
        })

    if conn: conn.close()
    ranked.sort(key=lambda x: (x["eligible"], x["raw_score"]), reverse=True)
    return ranked


# ── Request schemas ───────────────────────────────────────────
class PathwayInput(BaseModel):
    """Pathway predictor input.
    Points already encodes english level, age, and work experience
    per the Australian Skilled Migration points test.
    """
    occupation: str = Field(default="", description="ANZSCO occupation code")
    state: Literal["NSW","VIC","QLD","WA","SA","TAS","ACT","NT"] = Field(default="NSW")
    points: int = Field(default=80, ge=60, le=140, description="Total points test score (includes english/age/experience)")


class ApprovalInput(BaseModel):
    """
    New model (model_xgboost.json) — 14 features.
    No Points field — model does not use points directly.
    English level maps to English Test Score: vocational/competent=0, proficient=10, superior=20.
    Count EOIs is auto-looked up from warehouse.db or df_raw.
    """
    visa_type: Literal["189", "190", "491"] = Field(
        default="491",
        description="189, 190, and 491 supported by this model."
    )
    occupation: str = Field(
        default="",
        description=""
    )
    state: Literal["NSW","VIC","QLD","WA","SA","TAS","ACT","NT"] = Field(default="NSW")
    english_level: Literal["competent","proficient","superior"] = Field(default="proficient")
    count_eois: Optional[int] = Field(
        default=50,
        description="Jumlah EOI dalam pool. Jika tidak diisi, default 50."
    )
    eoi_mode: Literal["auto", "manual"] = Field(
        default="auto",
        description="Mode of EOI calculation. If 'auto', backend will overwrite count_eois using state-specific CSV lookup."
    )


# ── Routes ────────────────────────────────────────────────────
@router.post("/pathway")
async def predict_pathway(body: PathwayInput):
    """
    POST /api/predict/pathway
    Input  : occupation, state, points
    Output : ranked visa pathway list + SHAP approximation
    Note   : points already encodes english/age/experience per AU points test.
    """
    from main import models
    model = models.get("pathway")
    if not model:
        return {"error": "Pathway model not loaded."}
    try:
        # ── Run GBM inference (features: occupation, state, points)
        df_primary = pd.DataFrame([{
            "occupation": body.occupation,
            "state":      body.state,
            "points":     body.points,
        }])
        probs   = model.predict_proba(df_primary)[0]
        classes = list(model.classes_)

        # ── classes are visa_state strings e.g. '189_National', '190_NSW' ...
        # If the current model still outputs numeric classes (old model),
        # map them; otherwise use strings directly.
        visa_map = {0: '189', 1: '190', 2: '491'}

        if classes and isinstance(classes[0], (int, np.integer)):
            # Legacy numeric classes — expand to visa×state
            synthetic_classes = []
            synthetic_probs   = []
            for visa_idx in range(3):
                visa_type = visa_map.get(visa_idx, str(visa_idx))
                for state_name in ALL_STATES + ['National']:
                    synthetic_classes.append(f"{visa_type}_{state_name}")
                    synthetic_probs.append(float(probs[visa_idx]) if visa_idx < len(probs) else 0.0)
        else:
            # New model — classes are already visa_state strings
            synthetic_classes = [str(c) for c in classes]
            synthetic_probs   = [float(p) for p in probs]

        # ── Build ranked list
        ranked = build_ranked_pathways(
            model,
            occupation=body.occupation,
            state=body.state,
            points=body.points,
            probs=synthetic_probs,
            classes=synthetic_classes
        )

        # ── class_probs: only state-relevant + ALL STATES + 189_National
        filtered = [
            (c, float(p))
            for c, p in zip(synthetic_classes, synthetic_probs)
            if c.endswith(f"_{body.state}") or c.endswith("_ALL STATES") or c == "189_National"
        ]
        filtered.sort(key=lambda x: x[1], reverse=True)

        if not filtered:
            filtered = [
                (c, float(p))
                for c, p in zip(synthetic_classes, synthetic_probs)
                if c.endswith("_National")
            ]

        class_probs   = {c: round(p, 4) for c, p in filtered}
        top_class_val = filtered[0][0] if filtered else "None"
        confidence    = round(filtered[0][1], 4) if filtered else 0.0

        # ── SHAP approximation via GBM feature importances
        shap_values = compute_shap(model)

        return {
            "model":       "pathway",
            "prediction":  top_class_val,
            "confidence":  confidence,
            "points":      body.points,
            "class_probs": class_probs,
            "top_pathway": ranked[0] if ranked else None,
            "pathways":    ranked,
            "shap_values": shap_values,
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(500, detail=f"Pathway inference error: {str(e)}")


@router.post("/approval")
async def predict_approval(body: ApprovalInput):
    """
    POST /api/predict/approval
    Uses new model_xgboost.json — 13 features, no Points input.
    Count EOIs is auto-looked up from warehouse.db.
    """
    from main import models
    xgb_model   = models.get("approval")
    occ_encoder = models.get("occ_encoder")

    if not xgb_model:
        return {"error": "Approval model not loaded. Place model_xgboost.json in backend/models/."}

    try:
        # 1. Encode occupation
        occ_known = True
        try:
            # Try exact match first
            occ_to_match = body.occupation.strip()
            occupation_enc = int(occ_encoder.transform([occ_to_match])[0])
            print(f"DEBUG: Exact match success for '{occ_to_match}'")
        except Exception as e:
            # Try partial match (ANZSCO code only)
            anzsco = body.occupation.split()[0]
            matches = [c for c in occ_encoder.classes_ if c.startswith(anzsco)]
            if matches:
                occupation_enc = int(occ_encoder.transform([matches[0]])[0])
                # If exact failed but anzsco worked, it's technically a match from the list
                occ_known = True 
                print(f"DEBUG: Partial match success for '{body.occupation}' -> '{matches[0]}'")
            else:
                occupation_enc = 0
                occ_known = False
                print(f"DEBUG: No match found for '{body.occupation}'")

        english_score = ENGLISH_SCORE_MAP.get(body.english_level, 0.0)

        # 2. Assign count_eois based on eoi_mode
        if body.eoi_mode == "auto":
            count_eois, eois_source = get_eoi_count_internal(
                body.occupation, body.visa_type, int(english_score), body.state
            )
        else:
            count_eois = body.count_eois if body.count_eois is not None else 50
            eois_source = "manual_input"

        # 3. Build feature vector
        df_xgb = build_xgb_input(
            occupation_enc=occupation_enc,
            visa_type=body.visa_type,
            state=body.state,
            english_level=body.english_level,
            count_eois=count_eois,
        )
        print(f"DEBUG: df_xgb input features:\n{df_xgb}")
        print(f"DEBUG: df_xgb NaN check:\n{df_xgb.isna().sum()}")

        # 4. Predict
        # binary:logistic → 1=LODGED, 0=NOT LODGED
        try:
            # Check for NaN in input
            if df_xgb.isna().any().any():
                print("WARNING: df_xgb contains NaN before prediction")
                df_xgb = df_xgb.fillna(0)

            # Attempt predict_proba
            proba = xgb_model.predict_proba(df_xgb)[0]
            
            # Defensive check: if proba is NaN or has length != 2
            if proba is None or len(proba) < 2 or np.isnan(proba).any():
                print(f"DEBUG: predict_proba returned invalid result: {proba}. Trying raw booster.")
                # Fallback to booster prediction (returns probability for logistic)
                raw_p = float(xgb_model.get_booster().inplace_predict(df_xgb)[0])
                proba = [1.0 - raw_p, raw_p]
                
            print(f"DEBUG: Final proba result: {proba}")
        except Exception:
            print(f"DEBUG: Prediction failed, using 0.5 fallback:\n{traceback.format_exc()}")
            proba = [0.5, 0.5]
            
        prob_lodged    = round(float(proba[1]), 4)
        prob_not_lodged = round(float(proba[0]), 4)
        pred           = 1 if prob_lodged >= 0.5 else 0
        prediction_label = "LODGED" if pred == 1 else "NOT LODGED"
        prediction_label = "LODGED" if pred == 1 else "NOT LODGED"

        # 5. Label
        # if prob_lodged >= 0.80:   label, color = "High — Likely Lodged",     "green"
        if prob_lodged >= 0.50: 
            label, color = "Likely Lodged","blue"
        else: 
            label, color = "Likely Not Lodged","orange"
        # elif prob_lodged >= 0.20: label, color = "Low-Moderate",              "orange"
        # else:                     label, color = "Low — Likely Not Lodged","red"

        # 6. Feature importance
        feat_imp = {}
        try:
            imp = xgb_model.feature_importances_
            feat_imp = {n: round(float(v), 4) for n, v in zip(XGB_FEATURE_NAMES, imp)}
            feat_imp = dict(sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[:10])
        except Exception:
            pass

        return {
            "model":            "approval_xgboost_json",
            "prediction":       pred,
            "prediction_label": prediction_label,
            "probability":      prob_lodged,
            "prob_lodged":      prob_lodged,
            "prob_not_lodged":   prob_not_lodged,
            "label":            label,
            "color":            color,
            "inputs": {
                "visa_type":          body.visa_type,
                "occupation":         body.occupation,
                "state":              body.state,
                "english_level":      body.english_level,
                "english_score":      english_score,
                "count_eois":         count_eois,
                "count_eois_source":  eois_source,
            },
            "occupation_known":       occ_known,
            "top_feature_importance": feat_imp,
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(500, detail=f"Approval inference error: {str(e)}")


@router.get("/approval/occupations")
async def list_occupations(q: str = ""):
    """
    GET /api/predict/approval/occupations?q=engineer
    Returns matching occupation strings from occ_encoder.
    """
    from main import models
    occ_encoder = models.get("occ_encoder")

    if not occ_encoder:
        # Fallback to OCCUPATIONS_LIST if encoder isn't loaded for some reason, though it should be.
        if not OCCUPATIONS_LIST:
            return {"occupations": [], "error": "Occupations list not loaded"}
        classes = OCCUPATIONS_LIST
    else:
        classes = [str(c) for c in occ_encoder.classes_]
    
    if q:
        ql = q.lower()
        # Match by name OR ANZSCO code
        classes = [c for c in classes if ql in c.lower()]
    
    return {"occupations": classes[:50], "total": len(classes)}


@router.get("/approval/threshold")
async def approval_threshold():
    from main import models
    return {"threshold": models.get("threshold", 0.5)}

def get_eoi_count_internal(occupation: str, visa_type: str, english_score: int, state: str) -> Tuple[int, str]:
    if DF_RAW_EOI is None:
        return 50, "fallback_default"
    try:
        occ_clean = occupation.strip()
        anzsco = occ_clean.split()[0] if occ_clean else ""
        
        # 1. Filter overall by status
        df_base = DF_RAW_EOI[DF_RAW_EOI["EOI Status"] == "SUBMITTED"]
        
        # 2. Filter by occupation (Exact or ANZSCO)
        mask_occ = (df_base["Occupation"] == occ_clean)
        if not mask_occ.any() and anzsco:
            mask_occ = df_base["Occupation"].str.startswith(anzsco, na=False)
        
        df_occ_filtered = df_base[mask_occ]
        
        if df_occ_filtered.empty:
            return 50, "fallback_default_no_match"
            
        # 3. Get unique months descending (newest first)
        months = sorted(df_occ_filtered["As At Month"].unique(), reverse=True)
        
        # 4. Iterative month-by-month exact search (Back-searching)
        for month in months:
            df_m = df_occ_filtered[df_occ_filtered["As At Month"] == month]
            
            # Helper filters for this month
            m_visa = df_m["Visa Type"].str.contains(visa_type, na=False)
            m_eng  = df_m["English Test Score"] == english_score
            m_state = df_m["State"].astype(str).str.upper() == state.upper()
            
            df_exact = df_m[m_visa & m_eng & m_state]
            if not df_exact.empty:
                # Found exact match in this month
                # Summing just in case, though criteria is specific
                return int(df_exact["Count EOIs"].sum()), f"csv_exact_{month}"
        
        # 5. Final Fallback: If no exact match in ANY month, 
        # we check if there's any record for THAT SPECIFIC state.
        df_state = df_occ_filtered[df_occ_filtered["State"].astype(str).str.upper() == state.upper()]
        if not df_state.empty:
            latest_row = df_state.sort_values(by="As At Month", ascending=False).iloc[0]
            return int(latest_row["Count EOIs"]), f"csv_latest_state_fallback_{latest_row['As At Month']}"
            
        # Jika tidak ada sama sekali di state tersebut, kembalikan 0 agar tidak mencuri EOI dari state lain.
        return 0, "csv_no_match"
        
    except Exception as e:
        print(f"Error computing EOI count: {e}")
        return 50, "fallback_error"

@router.get("/approval/eoi_count")
async def api_get_eoi_count(occupation: str, visa_type: str, english_score: int = 10, state: str = ""):
    """
    GET /api/predict/approval/eoi_count?occupation=...&visa_type=...&english_score=...&state=...
    Cascading match for EOI count.
    """
    count, source = get_eoi_count_internal(occupation, visa_type, english_score, state)
    return {"count": count, "source": source, "error": ("CSV not loaded" if source == "fallback_default" else None)}