
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db.database import get_db
from cache.redis_client import get_cache, set_cache
from config import settings
import json
from fastapi.encoders import jsonable_encoder

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint for readiness/liveness probes."""
    return {"status": "ok"}

"""
routers/data.py
GET /api/data/* — query migration_db (MySQL) via SQLAlchemy
Redis cache: HIT → return immediately, MISS → query DB → cache → return
"""


# ── /api/data/summary ─────────────────────────────────────────
@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    """Dashboard KPIs — Redis cached 5 min."""
    cache_key = "data:summary"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    # Query EOI table
    try:
        # Latest snapshot month
        latest = await db.execute(text("""
            SELECT as_at_str, as_at_year, as_at_month_no
            FROM eoi_records
            ORDER BY as_at_year DESC, as_at_month_no DESC
            LIMIT 1
        """))
        latest_row = latest.fetchone()
        latest_month = latest_row[0] if latest_row else "N/A"

        # Total EOI pool (SUBMITTED) and Monthly Net Change in latest month
        pool = await db.execute(text("""
            WITH MonthlyCounts AS (
                SELECT 
                    as_at_str,
                    as_at_year,
                    as_at_month_no,
                    SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END) AS submitted_total
                FROM eoi_records
                WHERE eoi_status = 'SUBMITTED'
                GROUP BY as_at_str, as_at_year, as_at_month_no
            ),
            WithLag AS (
                SELECT 
                    as_at_str,
                    submitted_total,
                    submitted_total - LAG(submitted_total) OVER (ORDER BY as_at_year, as_at_month_no) AS net_change,
                    LAG(submitted_total) OVER (ORDER BY as_at_year, as_at_month_no) AS prev_total
                FROM MonthlyCounts
            )
            SELECT submitted_total, net_change, prev_total
            FROM WithLag
            WHERE as_at_str = :month
        """), {"month": latest_month})
        pool_row = pool.fetchone()
        eoi_pool = int(pool_row[0] or 0) if pool_row else 0
        net_change = int(pool_row[1] or 0) if pool_row else 0
        prev_eoi_pool = int(pool_row[2] or 0) if pool_row else 0

        # Direct INVITED count for the latest snapshot
        # This is the real count of people currently in INVITED status — always accurate.
        # pipeline_delta is tracked separately for trend context.
        inv_direct = await db.execute(text("""
            SELECT
                SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END)
            FROM eoi_records
            WHERE eoi_status = 'INVITED'
            AND as_at_str = :month
        """), {"month": latest_month})
        total_invitations = int(inv_direct.scalar() or 0)

        # Pipeline total (INVITED + LODGED) and its month-on-month delta for context
        inv_pipeline = await db.execute(text("""
            WITH MonthlyPipeline AS (
                SELECT
                    as_at_str,
                    as_at_year,
                    as_at_month_no,
                    SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END) AS pipeline_total
                FROM eoi_records
                WHERE eoi_status IN ('INVITED', 'LODGED')
                AND visa_type IN ('190', '491')
                GROUP BY as_at_str, as_at_year, as_at_month_no
            ),
            WithLag AS (
                SELECT
                    as_at_str,
                    pipeline_total,
                    pipeline_total - LAG(pipeline_total) OVER (ORDER BY as_at_year, as_at_month_no) AS pipeline_delta
                FROM MonthlyPipeline
            )
            SELECT pipeline_total, pipeline_delta
            FROM WithLag
            WHERE as_at_str = :month
        """), {"month": latest_month})
        inv_row = inv_pipeline.fetchone()
        pipeline_total = int(inv_row[0] or 0) if inv_row else 0
        pipeline_delta = int(inv_row[1] or 0) if inv_row else 0
        invitation_note = "growing" if pipeline_delta >= 0 else "pipeline_shrank"

        # Highest points cutoff (max points of INVITED)
        cutoff = await db.execute(text("""
            SELECT MAX(points)
            FROM eoi_records
            WHERE eoi_status = 'INVITED'
            AND TRIM(as_at_str) = :month
        """), {"month": latest_month})
        points_cutoff = int(cutoff.scalar() or 0)

        # Unique occupations in latest snapshot
        occ_count = await db.execute(text("""
            SELECT COUNT(DISTINCT anzsco_code)
            FROM eoi_records
            WHERE (anzsco_code IS NOT NULL AND anzsco_code != '')
            AND TRIM(as_at_str) = :month
        """), {"month": latest_month})
        shortage_occupations = int(occ_count.scalar() or 0)

        data = {
            "eoi_pool":              eoi_pool,
            "prev_eoi_pool":         prev_eoi_pool,        # Previous month SUBMITTED pool
            "net_pool_change":       net_change,
            "estimated_new_eois":    net_change,           # Formula 1: Net growth = New EOIs submitted (lower bound)
            "total_invitations":     total_invitations,   # direct INVITED count for latest snapshot
            "pipeline_total":        pipeline_total,      # INVITED + LODGED total
            "pipeline_delta":        pipeline_delta,      # month-on-month pipeline change
            "invitation_note":       invitation_note,
            "points_cutoff":         points_cutoff,
            "shortage_occupations":  shortage_occupations,
            "latest_snapshot":       latest_month,
            "source":                "migration_db (MySQL) → eoi_records",
        }

    except Exception as e:
        # Table doesn't exist yet — return info message
        data = {
            "eoi_pool":             0,
            "net_pool_change":      0,
            "estimated_new_eois":   0,
            "total_invitations":    0,
            "points_cutoff":        0,
            "shortage_occupations": 0,
            "latest_snapshot":      "N/A",
            "source":               "mock — run EOI ingestor first",
            "error":                str(e),
        }

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_DEFAULT_TTL)
    return data



# ── /api/data/quota ───────────────────────────────────────────
@router.get("/quota")
async def get_quota(db: AsyncSession = Depends(get_db)):
    """Migration quota data — from migration_db (MySQL) quota tables."""
    cache_key = "data:quota"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        # Latest planning year in DB
        latest_year_q = await db.execute(text("""
            SELECT planning_year FROM state_nomination_quotas
            ORDER BY planning_year DESC LIMIT 1
        """))
        latest_year_row = latest_year_q.fetchone()
        latest_year = latest_year_row[0] if latest_year_row else "2024-25"

        # State allocation for latest year
        state_q = await db.execute(text("""
            SELECT state, visa_type, quota_amount
            FROM state_nomination_quotas
            WHERE planning_year = :year
            ORDER BY state
        """), {"year": latest_year})
        state_rows = state_q.fetchall()

        # Pivot state data into {state: {visa_190, visa_491, total}}
        state_map: dict = {}
        for r in state_rows:
            state, visa, amount = r[0], r[1], r[2] or 0
            if state not in state_map:
                state_map[state] = {"state": state, "visa_190": 0, "visa_491": 0, "total": 0}
            if visa == "190":
                state_map[state]["visa_190"] = amount
            elif visa == "491":
                state_map[state]["visa_491"] = amount
            state_map[state]["total"] = state_map[state]["visa_190"] + state_map[state]["visa_491"]

        state_allocation = sorted(state_map.values(), key=lambda x: x["total"], reverse=True)

        # National planning levels — all years
        nat_q = await db.execute(text("""
            SELECT planning_year, visa_stream, visa_category, quota_amount
            FROM national_migration_quotas
            ORDER BY planning_year, visa_stream, visa_category
        """))
        nat_rows = nat_q.fetchall()

        # Pivot national data by year
        nat_map: dict = {}
        for r in nat_rows:
            yr, stream, cat, amount = r[0], r[1], r[2], r[3]
            if yr not in nat_map:
                nat_map[yr] = {"year": yr}
            # Map category names to clean keys
            key = cat.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "").replace("1","").replace("2","").strip("_")
            nat_map[yr][key] = amount

        national_planning = sorted(nat_map.values(), key=lambda x: x["year"])

        # Get migration totals from nat_map if available
        # This acts as the official planning level (the ceiling)
        nat_data_latest = nat_map.get(latest_year, {})
        
        # 1. Skilled Independent (189) - only in national table
        # Key: 'skilled_independent_subclass_89' (due to 1 removal)
        total_189 = nat_data_latest.get("skilled_independent_subclass_89", 0)
        
        # 2. State Nominated (190)
        # We prefer the sum of specific state allocations (state_nomination_quotas)
        # but fallback to national planning level if sum is 0
        sum_190 = sum(s["visa_190"] for s in state_allocation)
        total_190 = sum_190 if sum_190 > 0 else nat_data_latest.get("state_territory_nominated", 0)
        
        # 3. Skilled Work Regional (491)
        # Prefer sum of state allocations, fallback to national level
        sum_491 = sum(s["visa_491"] for s in state_allocation)
        total_491 = sum_491 if sum_491 > 0 else nat_data_latest.get("skilled_work_regional_provisional_subclass_49", 0)

        # 4. Overall Totals
        skill_total = nat_data_latest.get("skill_total", 0)
        migration_total = nat_data_latest.get("total_migration_program", 0)

        data = {
            "latest_year": latest_year,
            "total_189_quota": total_189,
            "total_190_quota": total_190,
            "total_491_quota": total_491,
            "total_state_quota": total_190 + total_491,
            "total_skill_quota": skill_total,
            "total_migration_quota": migration_total,
            "state_allocation": state_allocation,
            "national_planning": national_planning,
        }

    except Exception as e:
        data = {
            "latest_year": "N/A",
            "total_190_quota": 0,
            "total_491_quota": 0,
            "total_state_quota": 0,
            "total_skill_quota": 0,
            "total_migration_quota": 0,
            "state_allocation": [],
            "national_planning": [],
            "error": str(e),
        }

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data


# ── /api/data/eoi ─────────────────────────────────────────────
@router.get("/eoi")
async def get_eoi(
    year:   int = Query(None),
    state:  str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """EOI records — filter by year, state, status."""
    cache_key = f"data:eoi:{year}:{state}:{status}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        # Build dynamic query
        conditions = []
        params = {}
        if year:
            conditions.append("as_at_year = :year")
            params["year"] = year
        if state:
            conditions.append("state = :state")
            params["state"] = state.upper()
        if status:
            conditions.append("eoi_status = :status")
            params["status"] = status.upper()

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Summary by occupation + status
        result = await db.execute(text(f"""
            SELECT
                anzsco_code,
                occupation_name,
                visa_type,
                eoi_status,
                state,
                as_at_str,
                as_at_year,
                SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END) as total_eois,
                MIN(points) as min_points,
                MAX(points) as max_points,
                COUNT(*) as row_count
            FROM eoi_records
            {where}
            GROUP BY anzsco_code, occupation_name, visa_type, eoi_status, state, as_at_str, as_at_year
            ORDER BY as_at_year DESC, total_eois DESC
            LIMIT 500
        """), params)

        rows = result.fetchall()
        data = {
            "count": len(rows),
            "filters": {"year": year, "state": state, "status": status},
            "records": [
                {
                    "anzsco_code":     r[0],
                    "occupation_name": r[1],
                    "visa_type":       r[2],
                    "eoi_status":      r[3],
                    "state":           r[4],
                    "as_at_str":       r[5],
                    "as_at_year":      r[6],
                    "total_eois":      r[7],
                    "min_points":      r[8],
                    "max_points":      r[9],
                }
                for r in rows
            ],
        }

    except Exception as e:
        data = {"count": 0, "records": [], "error": str(e), "source": "run EOI ingestor first"}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_DEFAULT_TTL)
    return data


# ── /api/data/eoi/monthly ─────────────────────────────────────
@router.get("/eoi/monthly")
async def get_eoi_monthly(db: AsyncSession = Depends(get_db)):
    """EOI pool + invitations per month — for trend chart."""
    cache_key = "data:eoi:monthly"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            WITH MonthlySubmitted AS (
                SELECT
                    as_at_str,
                    as_at_year,
                    as_at_month_no,
                    SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END) as total
                FROM eoi_records
                WHERE eoi_status = 'SUBMITTED'
                GROUP BY as_at_str, as_at_year, as_at_month_no
            ),
            SubmittedWithLag AS (
                SELECT
                    as_at_str,
                    as_at_year,
                    as_at_month_no,
                    total as raw_pool,
                    total - LAG(total) OVER (ORDER BY as_at_year, as_at_month_no) as net_change
                FROM MonthlySubmitted
            ),
            PipelineByMonth AS (
                SELECT
                    as_at_str,
                    as_at_year,
                    as_at_month_no,
                    SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END) AS pipeline_total
                FROM eoi_records
                WHERE eoi_status IN ('INVITED', 'LODGED')
                -- Exclude Visa 189 from delta calc: it only exists in 2 months,
                -- causing false -85k swings when compared to months without 189 data.
                AND visa_type IN ('190', '491')
                GROUP BY as_at_str, as_at_year, as_at_month_no
            ),
            PipelineWithLag AS (
                SELECT
                    as_at_str,
                    as_at_year,
                    as_at_month_no,
                    pipeline_total,
                    pipeline_total - LAG(pipeline_total) OVER (ORDER BY as_at_year, as_at_month_no) AS pipeline_delta
                FROM PipelineByMonth
            )
            SELECT 
                s.as_at_str,
                s.as_at_year,
                s.as_at_month_no,
                COALESCE(s.net_change, 0) as net_change,
                COALESCE(p.pipeline_delta, 0) as pipeline_delta,
                s.raw_pool,
                COALESCE(p.pipeline_total, 0) as pipeline_total
            FROM SubmittedWithLag s
            LEFT JOIN PipelineWithLag p ON s.as_at_str = p.as_at_str
            ORDER BY s.as_at_year, s.as_at_month_no
        """))
        rows = result.fetchall()

        months = []
        for r in rows:
            pipeline_delta = r[4] or 0
            # Only show positive delta as estimated invitations — negative means pipeline shrank
            estimated_inv = pipeline_delta if pipeline_delta > 0 else None
            months.append({
                "month": r[0],
                "year": r[1],
                "month_no": r[2],
                "net_change": r[3] or 0,
                "invitations": estimated_inv,
                "pipeline_delta": pipeline_delta,
                "pipeline_total": r[6] or 0,
                "raw_pool": r[5] or 0,
            })

        data = {
            "count": len(months),
            "records": months,
        }

    except Exception as e:
        data = {"count": 0, "records": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_DEFAULT_TTL)
    return data


# ── /api/data/eoi/occupations ─────────────────────────────────

# Pagination with offset/limit
@router.get("/eoi/occupations")
async def get_eoi_occupations(
    year:      int = Query(None),
    state:     str = Query(None),
    visa_type: str = Query(None),
    search:    str = Query(None),
    page:      int = Query(1, ge=1),
    sort_by:   str = Query("invitations"),
    db: AsyncSession = Depends(get_db)
):
    """Paginated occupations by EOI pool size + invitation delta (50 per page)."""
    page_size = 50
    offset = (page - 1) * page_size
    cache_key = f"data:eoi:occupations:flow:{year}:{state}:{visa_type}:{search}:page{page}:sort{sort_by}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        if year:
            time_q = await db.execute(text(
                "SELECT DISTINCT as_at_str FROM eoi_records WHERE as_at_year = :yr ORDER BY as_at_month_no DESC LIMIT 2"
            ), {"yr": year})
        else:
            time_q = await db.execute(text(
                "SELECT DISTINCT as_at_str FROM eoi_records ORDER BY as_at_year DESC, as_at_month_no DESC LIMIT 2"
            ))
            
        time_rows = time_q.fetchall()
        if not time_rows:
            return {"count": 0, "records": [], "page": page, "total_pages": 1}
            
        snapshot_month = time_rows[0][0]
        prev_snapshot = time_rows[1][0] if len(time_rows) > 1 else None

        params = {"snapshot": snapshot_month}
        where_parts = ["as_at_str = :snapshot"]
        
        if state:
            params["state"] = state.upper()
            where_parts.append("state = :state")
        if visa_type:
            params["visa"] = visa_type
            where_parts.append("visa_type = :visa")
        if search:
            params["search"] = f"{search}%"
            where_parts.append("(occupation_name LIKE :search OR anzsco_code LIKE :search)")

        where = " AND ".join(where_parts)

        # 1. Total Count based on LATEST SNAPSHOT
        count_query = f"""
        SELECT COUNT(DISTINCT anzsco_code)
        FROM eoi_records
        WHERE {where}
        AND (count_eois > 0 OR count_eois = -1)
        """
        count_result = await db.execute(text(count_query), params)
        total_count = count_result.scalar() or 0
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

        if total_count == 0:
            return {"count": 0, "page": page, "page_size": page_size, "total_pages": 1, "records": []}

        # 2. Get subset of ANZSCO codes for this page
        params["limit"] = page_size
        params["offset"] = offset
        
        sort_expr = "MAX(occupation_name)"
        if sort_by == "pool":
            sort_expr = "SUM(CASE WHEN eoi_status = 'SUBMITTED' THEN CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) DESC, MAX(occupation_name)"
        elif sort_by == "invitations":
            sort_expr = "SUM(CASE WHEN eoi_status = 'INVITED' THEN CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) DESC, MAX(occupation_name)"
        elif sort_by == "rate":
            sort_expr = "SUM(CASE WHEN eoi_status = 'INVITED' THEN CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) / (SUM(CASE WHEN eoi_status = 'SUBMITTED' THEN CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) + SUM(CASE WHEN eoi_status IN ('INVITED', 'LODGED') THEN CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) + 0.0001) DESC, MAX(occupation_name)"

        distinct_query = f"""
        SELECT anzsco_code, MAX(occupation_name)
        FROM eoi_records
        WHERE {where}
        AND (count_eois > 0 OR count_eois = -1)
        GROUP BY anzsco_code
        ORDER BY {sort_expr}
        LIMIT :limit OFFSET :offset
        """
        distinct_result = await db.execute(text(distinct_query), params)
        occupation_rows = distinct_result.fetchall()

        if not occupation_rows:
            return {"count": total_count, "page": page, "total_pages": total_pages, "records": []}

        # 3. Aggregate Current AND Previous snapshot for these exact codes
        anzsco_list = [r[0] for r in occupation_rows]
        anzsco_placeholders = ",".join([f":anzsco_{i}" for i in range(len(anzsco_list))])
        for i, code in enumerate(anzsco_list):
            params[f"anzsco_{i}"] = code

        # To calculate Delta, we check both snapshots
        if prev_snapshot:
            params["prev_snapshot"] = prev_snapshot
            time_filter = "as_at_str IN (:snapshot, :prev_snapshot)"
        else:
            time_filter = "as_at_str = :snapshot"

        # Cleanly aggregate the current vs previous values
        agg_query = f"""
        SELECT
            anzsco_code,
            MAX(occupation_name) as occupation_name,
            
            -- Current Pool
            SUM(CASE WHEN as_at_str = :snapshot AND eoi_status = 'SUBMITTED' THEN 
                CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) as pool_curr,
            
            -- Previous Pool
            SUM(CASE WHEN as_at_str = :prev_snapshot AND eoi_status = 'SUBMITTED' THEN 
                CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) as pool_prev,

            -- Current Pipeline (INVITED + LODGED)
            SUM(CASE WHEN as_at_str = :snapshot AND eoi_status IN ('INVITED', 'LODGED') THEN 
                CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) as pipe_curr,
                
            -- Previous Pipeline
            SUM(CASE WHEN as_at_str = :prev_snapshot AND eoi_status IN ('INVITED', 'LODGED') THEN 
                CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) as pipe_prev,

            SUM(CASE WHEN as_at_str = :snapshot AND eoi_status = 'INVITED' THEN 
                CASE WHEN count_eois = -1 THEN 10 ELSE COALESCE(count_eois, 0) END ELSE 0 END) as invited_curr,

            MAX(CASE WHEN as_at_str = :snapshot AND eoi_status = 'INVITED' THEN points ELSE 0 END) as max_invited_points,
            COALESCE(MIN(CASE WHEN as_at_str = :snapshot AND eoi_status = 'INVITED' THEN points ELSE NULL END), 0) as min_invited_points,
            COUNT(DISTINCT CASE WHEN as_at_str = :snapshot THEN state END) as state_count,
            GROUP_CONCAT(DISTINCT CASE WHEN as_at_str = :snapshot THEN visa_type END) as visa_types
        FROM eoi_records
        WHERE {time_filter}
        AND anzsco_code IN ({anzsco_placeholders})
        GROUP BY anzsco_code
        ORDER BY pipe_curr DESC, pool_curr DESC, occupation_name
        """

        try:
           del params['limit']
           del params['offset']
        except: pass

        agg_result = await db.execute(text(agg_query), params)
        rows = agg_result.fetchall()

        records = []
        for r in rows:
            pool_curr = int(r[2] or 0)
            pool_prev = int(r[3] or 0)
            pipe_curr = int(r[4] or 0)
            pipe_prev = int(r[5] or 0)
            invited_curr = int(r[6] or 0)  # Current INVITED count for this occupation
            
            net_growth = pool_curr - pool_prev
            new_invitations = max(0, pipe_curr - pipe_prev)
            
            records.append({
                "anzsco_code":        r[0],
                "occupation_name":    r[1],
                "pool":               pool_curr,
                "net_growth":         net_growth,
                "pipeline_total":     pipe_curr,
                "new_invitations":    new_invitations,
                "current_invitations": invited_curr,
                "max_invited_points": int(r[7] or 0),
                "min_invited_points": int(r[8] or 0),
                "invitation_rate":    round(invited_curr / pool_curr, 3) if pool_curr > 0 else 0,
                "states":             int(r[9] or 0),
                "visa_types":         [v for v in (r[10].split(",") if r[10] else []) if v],
            })

        # Re-sort python-side by new_invitations to ensure top active ones are accurately sorted 
        # (Since SQL sorted by pipe_curr)
        records.sort(key=lambda x: (x['new_invitations'], x['pipeline_total']), reverse=True)

        data = {
            "count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "records": records,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        data = {"count": 0, "records": [], "error": str(e), "page": page, "page_size": page_size, "total_pages": 1}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data
    

# ── /api/data/row-count ──────────────────────────────────────
@router.get("/row-count")
async def get_row_count(db: AsyncSession = Depends(get_db)):
    """Total row count in eoi_records table — for dashboard status display."""
    cache_key = "data:row_count"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            SELECT COUNT(*) FROM eoi_records
        """))
        total_rows = int(result.scalar() or 0)
        
        # Format as human-readable (e.g., 8.3M, 1.2K)
        if total_rows >= 1_000_000:
            formatted = f"{total_rows / 1_000_000:.1f}M"
        elif total_rows >= 1_000:
            formatted = f"{total_rows / 1_000:.1f}K"
        else:
            formatted = str(total_rows)
        
        data = {
            "total_rows": total_rows,
            "formatted": formatted,
            "database": "migration_db (MySQL)",
        }
    except Exception as e:
        data = {
            "total_rows": 0,
            "formatted": "0",
            "database": "migration_db (MySQL)",
            "error": str(e),
        }

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_DEFAULT_TTL)
    return data


# ── /api/data/eoi/points ──────────────────────────────────────
@router.get("/eoi/points")
async def get_eoi_points(
    occupation: str = Query(None),
    visa_type:  str = Query(None),
    state:      str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Points distribution — for points cutoff chart."""
    cache_key = f"data:eoi:points:{occupation}:{visa_type}:{state}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        conditions = ["eoi_status IN ('SUBMITTED','INVITED')"]
        params = {}

        # Default to latest snapshot month — prevents scanning all historical data
        latest_q = await db.execute(text(
            "SELECT as_at_str FROM eoi_records ORDER BY as_at_year DESC, as_at_month_no DESC LIMIT 1"
        ))
        latest_row = latest_q.fetchone()
        if latest_row:
            conditions.append("as_at_str = :latest_month")
            params["latest_month"] = latest_row[0]

        if occupation:
            conditions.append("anzsco_code = :occupation")
            params["occupation"] = occupation
        if visa_type:
            conditions.append("visa_type = :visa_type")
            params["visa_type"] = visa_type
        if state:
            conditions.append("state = :state")
            params["state"] = state.upper()

        where = "WHERE " + " AND ".join(conditions)

        result = await db.execute(text(f"""
            SELECT
                points,
                eoi_status,
                SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END) as total
            FROM eoi_records
            {where}
            GROUP BY points, eoi_status
            ORDER BY points
        """), params)

        rows = result.fetchall()
        data = {
            "count": len(rows),
            "records": [
                {"points": r[0], "status": r[1], "total": int(r[2] or 0)}
                for r in rows
            ],
        }

    except Exception as e:
        data = {"count": 0, "records": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_DEFAULT_TTL)
    return data


# ── /api/data/shortage-heatmap ────────────────────────────────
@router.get("/shortage-heatmap")
async def get_shortage_heatmap(
    year: int = Query(2025, ge=2021, le=2026),
    db: AsyncSession = Depends(get_db)
):
    cache_key = f"data:shortage_heatmap:{year}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            SELECT anzsco_code, occupation_name, skill_level, skill_level_desc,
                   national, nsw, vic, qld, sa, wa, tas, nt, act, shortage_state_count
            FROM osl_shortage
            WHERE year = :year
            ORDER BY shortage_state_count DESC, national DESC, occupation_name
        """), {"year": year})
        rows = result.fetchall()

        # Summary stats
        total = len(rows)
        national_shortage = sum(1 for r in rows if r[4] == 1)
        by_skill = {}
        for r in rows:
            sl = r[2]
            if sl not in by_skill:
                by_skill[sl] = {"skill_level": sl, "desc": r[3], "total": 0, "shortage": 0}
            by_skill[sl]["total"] += 1
            if r[4] == 1:
                by_skill[sl]["shortage"] += 1

        # State shortage counts
        states = ["nsw","vic","qld","sa","wa","tas","nt","act"]
        state_counts = {}
        for r in rows:
            for i, s in enumerate(states):
                val = r[5+i]
                if val == 1:
                    state_counts[s.upper()] = state_counts.get(s.upper(), 0) + 1

        data = {
            "year": year,
            "total_occupations": total,
            "national_shortage_count": national_shortage,
            "national_shortage_pct": round(national_shortage/total*100, 1) if total else 0,
            "by_skill_level": sorted(by_skill.values(), key=lambda x: x["skill_level"]),
            "state_shortage_counts": state_counts,
            "records": [
                {
                    "anzsco_code": r[0], "occupation_name": r[1],
                    "skill_level": r[2], "skill_level_desc": r[3],
                    "national": r[4],
                    "nsw": r[5], "vic": r[6], "qld": r[7], "sa": r[8],
                    "wa": r[9], "tas": r[10], "nt": r[11], "act": r[12],
                    "shortage_state_count": r[13],
                }
                for r in rows
            ],
        }
    except Exception as e:
        data = {"year": year, "total_occupations": 0, "national_shortage_count": 0,
                "records": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data


# ── /api/data/employment-projections ─────────────────────────
@router.get("/employment-projections")
async def get_employment_projections(db: AsyncSession = Depends(get_db)):
    cache_key = "data:employment_projections"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            SELECT anzsco_code, occupation_name, employment_2024,
                   projected_2029, projected_2034, growth_5yr_pct, growth_10yr_pct, sector
            FROM employment_projections
            ORDER BY growth_5yr_pct DESC
            LIMIT 100
        """))
        rows = result.fetchall()
        data = {
            "count": len(rows),
            "records": [
                {"anzsco_code": r[0], "occupation_name": r[1],
                 "employment_2024": r[2], "projected_2029": r[3], "projected_2034": r[4],
                 "growth_5yr_pct": r[5], "growth_10yr_pct": r[6], "sector": r[7]}
                for r in rows
            ],
        }
    except Exception as e:
        data = {"count": 0, "records": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data


# ── /api/data/migration-trends ───────────────────────────────
@router.get("/migration-trends")
async def get_migration_trends(db: AsyncSession = Depends(get_db)):
    cache_key = "data:migration_trends"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            SELECT financial_year, stream, SUM(grants) as total_grants, SUM(planning_level) as planning
            FROM migration_grants
            GROUP BY financial_year, stream
            ORDER BY financial_year, stream
        """))
        rows = result.fetchall()
        data = {
            "count": len(rows),
            "records": [
                {"financial_year": r[0], "stream": r[1], "grants": r[2], "planning_level": r[3]}
                for r in rows
            ],
        }
    except Exception as e:
        data = {"count": 0, "records": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data


# ── /api/data/visa-analytics ─────────────────────────────────
@router.get("/visa-analytics")
async def get_visa_analytics(db: AsyncSession = Depends(get_db)):
    cache_key = "data:visa_analytics"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            SELECT financial_year, visa_subclass, visa_name,
                   country, state, SUM(grants) as total
            FROM visa_grants
            GROUP BY financial_year, visa_subclass, visa_name, country, state
            ORDER BY financial_year DESC, total DESC
            LIMIT 200
        """))
        rows = result.fetchall()
        data = {
            "count": len(rows),
            "records": [
                {"financial_year": r[0], "visa_subclass": r[1], "visa_name": r[2],
                 "country": r[3], "state": r[4], "grants": r[5]}
                for r in rows
            ],
        }
    except Exception as e:
        data = {"count": 0, "records": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data





# ── /api/data/nero/{anzsco4} ──────────────────────────────────
@router.get("/nero/{anzsco4}")
async def get_nero(anzsco4: str, db: AsyncSession = Depends(get_db)):
    """NERO time series for one ANZSCO4 — Regional + Northern Australia."""
    cache_key = f"data:nero:{anzsco4}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        # Regional NERO — all time
        reg_q = await db.execute(text("""
            SELECT date, year, month, jsa_remoteness, nero_estimate
            FROM nero_regional
            WHERE anzsco4_code = :code
            ORDER BY date
        """), {"code": anzsco4})
        reg_rows = reg_q.fetchall()

        # Northern NERO — all time
        nth_q = await db.execute(text("""
            SELECT date, year, month, northern_australia, nero_estimate
            FROM nero_northern
            WHERE anzsco4_code = :code
            ORDER BY date
        """), {"code": anzsco4})
        nth_rows = nth_q.fetchall()

        # Pivot regional into {date: {Regional: X, Major City: Y}}
        reg_map: dict = {}
        for r in reg_rows:
            d = r[0]
            if d not in reg_map:
                reg_map[d] = {"date": d, "year": r[1], "month": r[2]}
            reg_map[d][r[3]] = r[4]

        regional_trend = sorted(reg_map.values(), key=lambda x: x["date"])

        # Northern series
        northern_trend = [
            {"date": r[0], "year": r[1], "month": r[2],
             "northern_australia": r[3], "nero_estimate": r[4]}
            for r in nth_rows
        ]

        # Latest values
        latest_reg = regional_trend[-1] if regional_trend else None
        latest_nth = northern_trend[-1] if northern_trend else None

        # YoY change (latest vs 12 months ago)
        def yoy(trend, key):
            if len(trend) < 13:
                return None
            latest_val = trend[-1].get(key, 0) or 0
            prev_val   = trend[-13].get(key, 0) or 0
            if prev_val == 0:
                return None
            return round((latest_val - prev_val) / prev_val * 100, 1)

        data = {
            "anzsco4_code": anzsco4,
            "regional_trend": regional_trend[-36:],   # last 3 years
            "northern_trend": northern_trend[-36:],
            "latest_regional": latest_reg,
            "latest_northern": latest_nth,
            "yoy_regional": yoy(regional_trend, "Regional"),
            "yoy_major_city": yoy(regional_trend, "Major City"),
            "total_datapoints": len(reg_rows) + len(nth_rows),
        }

    except Exception as e:
        data = {"anzsco4_code": anzsco4, "regional_trend": [],
                "northern_trend": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data



# ── /api/data/nero-sa4/{anzsco4} ─────────────────────────────
@router.get("/nero-sa4/{anzsco4}")
async def get_nero_sa4(
    anzsco4: str,
    db: AsyncSession = Depends(get_db)
):
    """NERO SA4-level breakdown for one ANZSCO4 — latest month only."""
    cache_key = f"data:nero_sa4:{anzsco4}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        # Per SA4 in latest month for this code
        sa4_q = await db.execute(text("""
            SELECT state_name, sa4_code, sa4_name, MAX(nsc_emp) as nsc_emp
            FROM nero_sa4
            WHERE anzsco4_code = :code
              AND date = (SELECT MAX(date) FROM nero_sa4 WHERE anzsco4_code = :code)
            GROUP BY state_name, sa4_code, sa4_name
            ORDER BY nsc_emp DESC
        """), {"code": anzsco4})
        sa4_rows = sa4_q.fetchall()
        
        # Latest date for metadata
        latest = None
        if sa4_rows:
            latest_q = await db.execute(text("SELECT MAX(date) FROM nero_sa4 WHERE anzsco4_code = :code"), {"code": anzsco4})
            latest = latest_q.scalar()
        
        if not sa4_rows:
            return {"anzsco4_code": anzsco4, "latest_date": None,
                    "by_state": [], "by_sa4": [], "error": "No nero_sa4 data — run nero_sa4_ingestor.py"}

        # Aggregate by state
        state_map: dict = {}
        for r in sa4_rows:
            s = r[0]
            if s not in state_map:
                state_map[s] = {"state": s, "nsc_emp": 0, "sa4_count": 0}
            state_map[s]["nsc_emp"] += r[3] or 0
            state_map[s]["sa4_count"] += 1

        # 12-month trend for top 5 SA4s
        top5_codes = [r[1] for r in sa4_rows[:5]]
        trend_rows = []
        if top5_codes:
            placeholders = ",".join([":c" + str(i) for i in range(len(top5_codes))])
            params = {"code": anzsco4, "latest": latest}
            params.update({f"c{i}": top5_codes[i] for i in range(len(top5_codes))})
            trend_q = await db.execute(text(f"""
                SELECT date, sa4_name, MAX(nsc_emp) as nsc_emp
                FROM nero_sa4
                WHERE anzsco4_code = :code
                  AND sa4_code IN ({placeholders})
                  AND date >= DATE_SUB(:latest, INTERVAL 1 YEAR)
                GROUP BY date, sa4_name
                ORDER BY date, sa4_name
            """), params)
            trend_rows = trend_q.fetchall()

        data = {
            "anzsco4_code": anzsco4,
            "latest_date": latest,
            "total_employment": sum(r[3] or 0 for r in sa4_rows),
            "by_state": sorted(state_map.values(), key=lambda x: x["nsc_emp"], reverse=True),
            "by_sa4": [
                {"state": r[0], "sa4_code": r[1], "sa4_name": r[2], "nsc_emp": r[3] or 0}
                for r in sa4_rows[:30]
            ],
            "top5_trend": [
                {"date": r[0], "sa4_name": r[1], "nsc_emp": r[2] or 0}
                for r in trend_rows
            ],
        }

    except Exception as e:
        data = {"anzsco4_code": anzsco4, "latest_date": None,
                "by_state": [], "by_sa4": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data

# ── /api/data/nero-summary ────────────────────────────────────
@router.get("/nero-summary")
async def get_nero_summary(db: AsyncSession = Depends(get_db)):
    """Top occupations by NERO in latest month — Regional & Northern."""
    cache_key = "data:nero_summary"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        # Latest date available
        latest_q = await db.execute(text("SELECT MAX(date) FROM nero_regional"))
        latest = latest_q.scalar()

        top_regional = await db.execute(text("""
            SELECT anzsco4_code, anzsco4_name, jsa_remoteness, nero_estimate
            FROM nero_regional
            WHERE date = :latest AND jsa_remoteness = 'Regional'
            ORDER BY nero_estimate DESC LIMIT 20
        """), {"latest": latest})

        top_northern = await db.execute(text("""
            SELECT anzsco4_code, anzsco4_name, northern_australia, nero_estimate
            FROM nero_northern
            WHERE date = (SELECT MAX(date) FROM nero_northern)
            ORDER BY nero_estimate DESC LIMIT 20
        """))

        data = {
            "latest_date": latest,
            "top_regional": [
                {"anzsco4_code": r[0], "anzsco4_name": r[1],
                 "remoteness": r[2], "nero_estimate": r[3]}
                for r in top_regional.fetchall()
            ],
            "top_northern": [
                {"anzsco4_code": r[0], "anzsco4_name": r[1],
                 "northern_australia": r[2], "nero_estimate": r[3]}
                for r in top_northern.fetchall()
            ],
        }

    except Exception as e:
        data = {"latest_date": None, "top_regional": [], "top_northern": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data

# ── /api/data/osl-trend ──────────────────────────────────────
@router.get("/osl-trend")
async def get_osl_trend(db: AsyncSession = Depends(get_db)):
    """Shortage trend 2021-2025 — national + per state + per skill level."""
    cache_key = "data:osl_trend"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        # National trend per year
        trend = await db.execute(text("""
            SELECT year,
                   COUNT(DISTINCT anzsco_code) as total,
                   SUM(national) as national_shortage,
                   SUM(nsw) as nsw, SUM(vic) as vic, SUM(qld) as qld,
                   SUM(sa) as sa, SUM(wa) as wa, SUM(tas) as tas,
                   SUM(nt) as nt, SUM(act) as act
            FROM osl_shortage
            GROUP BY year ORDER BY year
        """))
        trend_rows = trend.fetchall()
        yearly_trend = [
            {
                "year": r[0], "total": r[1], "national": r[2],
                "national_pct": round(r[2]/r[1]*100, 1) if r[1] else 0,
                "NSW": r[3], "VIC": r[4], "QLD": r[5],
                "SA": r[6], "WA": r[7], "TAS": r[8],
                "NT": r[9], "ACT": r[10],
            }
            for r in trend_rows
        ]

        # Top shortage occupations in latest year (2025)
        top = await db.execute(text("""
            SELECT anzsco_code, occupation_name, skill_level, skill_level_desc,
                   shortage_state_count, national
            FROM osl_shortage
            WHERE year = 2025 AND national = 1
            ORDER BY shortage_state_count DESC
            LIMIT 20
        """))
        top_rows = top.fetchall()
        top_shortages = [
            {"anzsco_code": r[0], "occupation_name": r[1],
             "skill_level": r[2], "skill_level_desc": r[3],
             "shortage_state_count": r[4], "national": r[5]}
            for r in top_rows
        ]

        # Skill level breakdown latest year
        skill = await db.execute(text("""
            SELECT skill_level, skill_level_desc,
                   COUNT(*) as total, SUM(national) as shortage
            FROM osl_shortage WHERE year = 2025
            GROUP BY skill_level, skill_level_desc ORDER BY skill_level
        """))
        skill_rows = skill.fetchall()
        skill_breakdown = [
            {"skill_level": r[0], "desc": r[1], "total": r[2], "shortage": r[3],
             "pct": round(r[3]/r[2]*100, 1) if r[2] else 0}
            for r in skill_rows
        ]

        data = {
            "yearly_trend": yearly_trend,
            "top_shortages_2025": top_shortages,
            "skill_breakdown": skill_breakdown,
        }

    except Exception as e:
        data = {"yearly_trend": [], "top_shortages_2025": [], "skill_breakdown": [], "error": str(e)}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_LONG_TTL)
    return data


# ── /api/data/occupation/{anzsco} ────────────────────────────
@router.get("/occupation/{anzsco}")
async def get_occupation_detail(anzsco: str, db: AsyncSession = Depends(get_db)):
    """Full detail for one occupation — EOI stats, state breakdown, points distribution."""
    cache_key = f"data:occupation:{anzsco}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        # Get latest 12 snapshot months for this occupation
        latest_months_q = await db.execute(text("""
            SELECT DISTINCT as_at_str, as_at_year, as_at_month_no
            FROM eoi_records
            WHERE anzsco_code = :anzsco
            ORDER BY as_at_year DESC, as_at_month_no DESC
            LIMIT 12
        """), {"anzsco": anzsco})
        latest_months_rows = latest_months_q.fetchall()
        if not latest_months_rows:
            return {"error": "Occupation not found", "anzsco": anzsco}

        # Tuple of latest 12 snapshot strings e.g. ('03/2026','02/2026',...)
        latest_12 = tuple(r[0] for r in latest_months_rows)
        # MySQL IN clause placeholder
        placeholders = ",".join(f":m{i}" for i in range(len(latest_12)))
        month_params = {f"m{i}": v for i, v in enumerate(latest_12)}

        info = await db.execute(text(f"""
            SELECT anzsco_code, occupation_name, visa_type,
                   COUNT(DISTINCT state) as state_count
            FROM eoi_records
            WHERE anzsco_code = :anzsco
            AND as_at_str IN ({placeholders})
            GROUP BY anzsco_code, occupation_name, visa_type
        """), {"anzsco": anzsco, **month_params})
        info_rows = info.fetchall()
        if not info_rows:
            return {"error": "Occupation not found", "anzsco": anzsco}

        occupation_name = info_rows[0][1]
        visa_types = list(set(r[2] for r in info_rows))

        # EOI summary by status — latest 12 months only
        eoi = await db.execute(text(f"""
            SELECT eoi_status,
                   SUM(CASE WHEN count_eois = -1 THEN 10 ELSE count_eois END) as total,
                   MIN(points) as min_pts, MAX(points) as max_pts, AVG(points) as avg_pts
            FROM eoi_records
            WHERE anzsco_code = :anzsco
            AND as_at_str IN ({placeholders})
            GROUP BY eoi_status
        """), {"anzsco": anzsco, **month_params})
        eoi_rows = eoi.fetchall()
        eoi_summary = {r[0]: {"total": int(r[1] or 0), "min_pts": r[2], "max_pts": r[3], "avg_pts": round(r[4] or 0, 1)} for r in eoi_rows}

        # State breakdown — latest 12 months only
        states = await db.execute(text(f"""
            SELECT state, visa_type,
                   SUM(CASE WHEN eoi_status='SUBMITTED' AND count_eois=-1 THEN 10 WHEN eoi_status='SUBMITTED' THEN count_eois ELSE 0 END) as pool,
                   SUM(CASE WHEN eoi_status='INVITED' AND count_eois=-1 THEN 10 WHEN eoi_status='INVITED' THEN count_eois ELSE 0 END) as invitations,
                   MAX(CASE WHEN eoi_status='INVITED' THEN points ELSE 0 END) as max_inv_pts,
                   MIN(CASE WHEN eoi_status='INVITED' THEN points ELSE NULL END) as min_inv_pts
            FROM eoi_records
            WHERE anzsco_code = :anzsco
            AND as_at_str IN ({placeholders})
            GROUP BY state, visa_type ORDER BY invitations DESC, pool DESC
        """), {"anzsco": anzsco, **month_params})
        state_rows = states.fetchall()
        state_breakdown = [
            {"state": r[0], "visa_type": r[1], "pool": int(r[2] or 0), "invitations": int(r[3] or 0),
             "max_invited_points": int(r[4] or 0), "min_invited_points": int(r[5] or 0),
             "invitation_rate": round(r[3]/r[2], 3) if r[2] and r[2] > 0 else 0,
             "is_open": int(r[3] or 0) > 0}
            for r in state_rows
        ]

        # Points distribution
        pts = await db.execute(text("""
            SELECT points, eoi_status,
                   SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END) as total
            FROM eoi_records
            WHERE anzsco_code = :anzsco
            AND as_at_year = (SELECT MAX(as_at_year) FROM eoi_records WHERE anzsco_code = :anzsco)
            AND eoi_status IN ('SUBMITTED','INVITED')
            GROUP BY points, eoi_status ORDER BY points
        """), {"anzsco": anzsco})
        pts_rows = pts.fetchall()
        pts_map: dict = {}
        for r in pts_rows:
            if r[0] not in pts_map:
                pts_map[r[0]] = {"points": r[0], "SUBMITTED": 0, "INVITED": 0}
            pts_map[r[0]][r[1]] = int(r[2] or 0)
        points_distribution = list(pts_map.values())

        # Monthly trend
        trend = await db.execute(text("""
            SELECT as_at_str, as_at_year, as_at_month_no, eoi_status,
                   SUM(CASE WHEN count_eois=-1 THEN 10 ELSE count_eois END) as total
            FROM eoi_records WHERE anzsco_code = :anzsco AND eoi_status IN ('SUBMITTED','INVITED')
            GROUP BY as_at_str, as_at_year, as_at_month_no, eoi_status
            ORDER BY as_at_year, as_at_month_no
        """), {"anzsco": anzsco})
        trend_rows = trend.fetchall()
        trend_map: dict = {}
        for r in trend_rows:
            k = r[0]
            if k not in trend_map:
                trend_map[k] = {"month": k, "year": r[1], "month_no": r[2], "pool": 0, "invitations": 0}
            if r[3] == "SUBMITTED": trend_map[k]["pool"] += r[4]
            elif r[3] == "INVITED": trend_map[k]["invitations"] += r[4]
        monthly_trend = sorted(trend_map.values(), key=lambda x: (x["year"], x["month_no"]))

        pool_total = eoi_summary.get("SUBMITTED", {}).get("total", 0)
        inv_total  = eoi_summary.get("INVITED",   {}).get("total", 0)

        # ── OSL Shortage (2021-2025) ──────────────────────────
        osl_q = await db.execute(text("""
            SELECT year, national, nsw, vic, qld, sa, wa, tas, nt, act,
                   shortage_state_count, skill_level, skill_level_desc
            FROM osl_shortage
            WHERE anzsco_code = :anzsco
            ORDER BY year
        """), {"anzsco": anzsco})
        osl_rows = osl_q.fetchall()
        osl_history = [
            {
                "year": r[0], "national": r[1],
                "NSW": r[2], "VIC": r[3], "QLD": r[4], "SA": r[5],
                "WA": r[6], "TAS": r[7], "NT": r[8], "ACT": r[9],
                "shortage_state_count": r[10],
                "skill_level": r[11], "skill_level_desc": r[12],
            }
            for r in osl_rows
        ] if osl_rows else None
        # Latest OSL status
        latest_osl = osl_history[-1] if osl_history else None

        # ── JSA Shortage ──────────────────────────────────────
        shortage_q = await db.execute(text("""
            SELECT DISTINCT anzsco_code, anzsco_name, shortage_rating, shortage_driver
            FROM jsa_shortage WHERE anzsco_code LIKE :prefix
            ORDER BY anzsco_level
        """), {"prefix": anzsco[:4] + "%"})
        shortage_rows = shortage_q.fetchall()
        shortage_data = [
            {"anzsco_code": r[0], "name": r[1], "rating": r[2], "driver": r[3]}
            for r in shortage_rows
        ] if shortage_rows else None

        # ── JSA Projected Employment ──────────────────────────
        proj_q = await db.execute(text("""
            SELECT DISTINCT projected_year, projected_change, occ_group
            FROM jsa_projected WHERE anzsco_code LIKE :prefix
            ORDER BY projected_year
        """), {"prefix": anzsco[:4] + "%"})
        proj_rows = proj_q.fetchall()
        employment_projection = [
            {"year": r[0], "change": r[1], "group": r[2]}
            for r in proj_rows
        ] if proj_rows else None

        # ── JSA Demographics ──────────────────────────────────
        demo_q = await db.execute(text("""
            SELECT DISTINCT category, segment, share
            FROM jsa_demographics WHERE anzsco_code LIKE :prefix
            ORDER BY category, segment
        """), {"prefix": anzsco[:4] + "%"})
        demo_rows = demo_q.fetchall()
        demographics = [
            {"category": r[0], "segment": r[1], "share": round(float(r[2] or 0), 3)}
            for r in demo_rows
        ] if demo_rows else None

        # ── JSA Job Ads Monthly (last 24 months) ──────────────
        ads_q = await db.execute(text("""
            SELECT job_ads_date, SUM(job_ads_count) as total
            FROM jsa_monthly_ads WHERE anzsco_code LIKE :prefix
            GROUP BY job_ads_date ORDER BY job_ads_date DESC LIMIT 24
        """), {"prefix": anzsco[:4] + "%"})
        ads_rows = ads_q.fetchall()
        job_vacancies = [
            {"date": r[0], "job_ads": int(r[1] or 0)}
            for r in reversed(ads_rows)
        ] if ads_rows else None

        # ── JSA Quarterly Employment ──────────────────────────
        emp_q = await db.execute(text("""
            SELECT quarter, SUM(employment) as total, AVG(vacancy_rate) as vr
            FROM jsa_quarterly_employment WHERE anzsco_code LIKE :prefix
            GROUP BY quarter ORDER BY quarter DESC LIMIT 12
        """), {"prefix": anzsco[:4] + "%"})
        emp_rows = emp_q.fetchall()
        workforce = [
            {"quarter": r[0], "employment": int(r[1] or 0), "vacancy_rate": round(float(r[2] or 0), 4)}
            for r in reversed(emp_rows)
        ] if emp_rows else None

        # ── JSA Education ─────────────────────────────────────
        edu_q = await db.execute(text("""
            SELECT DISTINCT field, edu_level, MAX(share) as share
            FROM jsa_education WHERE anzsco_code LIKE :prefix
            GROUP BY field, edu_level ORDER BY share DESC LIMIT 10
        """), {"prefix": anzsco[:4] + "%"})
        edu_rows = edu_q.fetchall()
        education = [
            {"field": r[0], "level": r[1], "share": round(float(r[2] or 0), 3)}
            for r in edu_rows
        ] if edu_rows else None

        # ── JSA Recruitment ───────────────────────────────────
        rec_q = await db.execute(text("""
            SELECT filled_vacancies, avg_applicants, avg_qualified,
                   avg_suitable, avg_experience, pct_require_exp
            FROM jsa_recruitment 
            WHERE anzsco_code = :anzsco OR anzsco_code LIKE :prefix 
            LIMIT 1
        """), {"anzsco": anzsco, "prefix": anzsco[:4] + "%"})
        rec_row = rec_q.fetchone()
        recruitment = {
            "filled_vacancies":  rec_row[0],
            "avg_applicants":    rec_row[1],
            "avg_qualified":     rec_row[2],
            "avg_suitable":      rec_row[3],
            "avg_experience":    rec_row[4],
            "pct_require_exp":   rec_row[5],
        } if rec_row else None

        # ── JSA Top 10 regions ────────────────────────────────
        top10_q = await db.execute(text("""
            SELECT DISTINCT rank_category, rank_position, sa4_name, value
            FROM jsa_top10 WHERE anzsco_code LIKE :prefix
            AND rank_category = 'Employment'
            ORDER BY rank_position LIMIT 10
        """), {"prefix": anzsco[:4] + "%"})
        top10_rows = top10_q.fetchall()
        top_regions = [
            {"rank": r[1], "region": r[2], "value": r[3]}
            for r in top10_rows
        ] if top10_rows else None

        data = {
            "anzsco_code": anzsco, "occupation_name": occupation_name,
            "visa_types": visa_types, "eoi_summary": eoi_summary,
            "pool_total": pool_total, "invitations_total": inv_total,
            "invitation_rate": round(inv_total/pool_total, 3) if pool_total > 0 else 0,
            "state_breakdown": state_breakdown,
            "points_distribution": points_distribution,
            "monthly_trend": monthly_trend,
            # OSL data
            "osl_history":            osl_history,
            "latest_osl":             latest_osl,
            # JSA data
            "shortage_data":          shortage_data,
            "employment_projection":  employment_projection,
            "demographics":           demographics,
            "job_vacancies":          job_vacancies,
            "workforce":              workforce,
            "education":              education,
            "recruitment":            recruitment,
            "top_regions":            top_regions,
        }

    except Exception as e:
        data = {"error": str(e), "anzsco": anzsco}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=settings.CACHE_DEFAULT_TTL)
    return data

# ── /api/data/shortage-forecast ──────────────────────────────
@router.get("/shortage-forecast")
async def get_shortage_forecast(
    state:     str = Query(None),
    limit:     int = Query(50, le=500),
    sort_year: int = Query(2026),
    search:    str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    ML-predicted shortage probabilities 2026–2030 from RandomForest model.
    Source: shortage_forecast table (ingested from Occupation_Shortage_Forecaster_2026_2030_Wide.csv).
    ✅ REAL DATA — not mock.
    """
    cache_key = f"data:shortage_forecast:{state}:{limit}:{sort_year}:{search}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    sort_col = f"prob_{sort_year}" if sort_year in (2026,2027,2028,2029,2030) else "prob_2026"

    try:
        conditions = []
        params: dict = {"limit": limit}
        if state:
            conditions.append("state = :state")
            params["state"] = state
        if search:
            conditions.append("(occupation LIKE :search OR anzsco_code LIKE :search)")
            params["search"] = f"%{search}%"
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        result = await db.execute(text(f"""
            SELECT anzsco_code, occupation, state,
                   prob_2026, prob_2027, prob_2028, prob_2029, prob_2030
            FROM shortage_forecast
            {where}
            ORDER BY {sort_col} DESC
            LIMIT :limit
        """), params)
        rows = result.fetchall()

        records = [
            {
                "anzsco_code": r[0],
                "occupation":  r[1],
                "state":       r[2],
                "prob_2026":   round(r[3], 4),
                "prob_2027":   round(r[4], 4),
                "prob_2028":   round(r[5], 4),
                "prob_2029":   round(r[6], 4),
                "prob_2030":   round(r[7], 4),
            }
            for r in rows
        ]
        data = {
            "source":    "ml_model",   # ✅ real — NOT mock
            "model":     "RandomForest — shortage_forecast table",
            "state":     state or "all",
            "sort_year": sort_year,
            "total":     len(records),
            "records":   records,
        }
    except Exception as e:
        data = {"source": "error", "error": str(e), "records": []}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=3600)
    return data


@router.get("/shortage-forecast/{anzsco_code}")
async def get_shortage_forecast_by_code(
    anzsco_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    5-year ML shortage forecast for one ANZSCO code across all states.
    Used by Occupation Detail → Projection tab.
    ✅ REAL DATA — not mock.
    """
    cache_key = f"data:shortage_forecast_code:{anzsco_code}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            SELECT anzsco_code, occupation, state,
                   prob_2026, prob_2027, prob_2028, prob_2029, prob_2030
            FROM shortage_forecast
            WHERE anzsco_code LIKE :prefix
            ORDER BY prob_2026 DESC
        """), {"prefix": anzsco_code + "%"})
        rows = result.fetchall()

        records = [
            {
                "anzsco_code": r[0],
                "occupation":  r[1],
                "state":     r[2],
                "prob_2026": round(r[3], 4),
                "prob_2027": round(r[4], 4),
                "prob_2028": round(r[5], 4),
                "prob_2029": round(r[6], 4),
                "prob_2030": round(r[7], 4),
            }
            for r in rows
        ]
        data = {
            "source":      "ml_model",
            "anzsco_code": anzsco_code,
            "occupation":  rows[0][1] if rows else None,
            "records":     records,
        }
    except Exception as e:
        data = {"source": "error", "anzsco_code": anzsco_code, "error": str(e), "records": []}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=3600)
    return data


# ── /api/data/shortage-unified ───────────────────────────────
@router.get("/shortage-unified")
async def get_shortage_unified(
    state:     str = Query(None),
    year:      int = Query(None),
    limit:     int = Query(100, le=1000),
    search:    str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified shortage data: OSL (2021-2025) + ML Forecast (2026-2030).
    Single source of truth for historical and predicted occupational shortages.
    """
    cache_key = f"data:shortage_unified:{state}:{year}:{limit}:{search}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        conditions = []
        params: dict = {"limit": limit}
        
        if state:
            conditions.append("state = :state")
            params["state"] = state.upper()
        if year:
            conditions.append("year = :year")
            params["year"] = year
        if search:
            conditions.append("(occupation_name LIKE :search OR anzsco_code LIKE :search)")
            params["search"] = f"%{search}%"
        
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        
        result = await db.execute(text(f"""
            SELECT anzsco_code, occupation_name, skill_level, year, state,
                   is_shortage, prob_shortage, source
            FROM shortage_unified
            {where}
            ORDER BY year DESC, state, anzsco_code
            LIMIT :limit
        """), params)
        rows = result.fetchall()

        records = [
            {
                "anzsco_code": r[0],
                "occupation_name": r[1],
                "skill_level": r[2],
                "year": r[3],
                "state": r[4],
                "is_shortage": r[5],
                "prob_shortage": round(r[6], 4) if r[6] else None,
                "source": r[7],
            }
            for r in rows
        ]
        
        data = {
            "source": "mysql",
            "type": "shortage_unified",
            "filters": {
                "state": state,
                "year": year,
                "search": search,
            },
            "total": len(records),
            "records": records,
        }
    except Exception as e:
        data = {"source": "error", "error": str(e), "records": []}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=3600)
    return data


# ── /api/data/shortage-unified/{anzsco_code} ─────────────────
@router.get("/shortage-unified/{anzsco_code}")
async def get_shortage_unified_by_code(
    anzsco_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete shortage history + forecast for one occupation across all states and years.
    Combines OSL (2021-2025) and ML forecast (2026-2030).
    """
    cache_key = f"data:shortage_unified_code:{anzsco_code}"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            SELECT anzsco_code, occupation_name, skill_level, year, state,
                   is_shortage, prob_shortage, source
            FROM shortage_unified
            WHERE anzsco_code = :code
            ORDER BY year DESC, state
        """), {"code": anzsco_code})
        rows = result.fetchall()

        # Group by state for easier visualization
        by_state = {}
        occupation_name = None
        skill_level = None
        
        for r in rows:
            state = r[4]
            year = r[3]
            
            if not occupation_name:
                occupation_name = r[1]
                skill_level = r[2]
            
            if state not in by_state:
                by_state[state] = {
                    "state": state,
                    "records": []
                }
            
            by_state[state]["records"].append({
                "year": year,
                "is_shortage": r[5],
                "prob_shortage": round(r[6], 4) if r[6] else None,
                "source": r[7],
            })
        
        data = {
            "anzsco_code": anzsco_code,
            "occupation_name": occupation_name,
            "skill_level": skill_level,
            "total_records": len(rows),
            "by_state": dict(sorted(by_state.items())),
        }
    except Exception as e:
        data = {"anzsco_code": anzsco_code, "error": str(e), "by_state": {}}

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=3600)
    return data


# ── /api/data/volume-forecast ────────────────────────────────
@router.get("/volume-forecast")
async def get_volume_forecast(
    db: AsyncSession = Depends(get_db),
):
    """
    Prophet migration volume forecast Jan 2026 – Dec 2030.
    Source: migration_volume_forecast table (60 monthly rows).
    Returns point forecast + 80% and 95% confidence intervals.
    """
    cache_key = "data:volume_forecast"
    cached = await get_cache(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    try:
        result = await db.execute(text("""
            SELECT month, year, month_no,
                   yhat, yhat_lower_95, yhat_upper_95,
                   yhat_lower_80, yhat_upper_80
            FROM migration_volume_forecast
            ORDER BY month
        """))
        rows = result.fetchall()

        records = [
            {
                "month":         r[0],
                "year":          r[1],
                "month_no":      r[2],
                "yhat":          round(r[3], 0),
                "yhat_lower_95": round(r[4], 0),
                "yhat_upper_95": round(r[5], 0),
                "yhat_lower_80": round(r[6], 0),
                "yhat_upper_80": round(r[7], 0),
            }
            for r in rows
        ]

        # Yearly aggregates for summary cards
        yearly: dict = {}
        for r in records:
            y = str(r["year"])
            if y not in yearly:
                yearly[y] = {"yhat": 0, "count": 0}
            yearly[y]["yhat"]  += r["yhat"]
            yearly[y]["count"] += 1
        yearly_totals = [
            {"year": y, "total": round(v["yhat"], 0), "months": v["count"]}
            for y, v in sorted(yearly.items())
        ]

        data = {
            "source":         "Prophet — migration_volume_forecast table",
            "model":          "Prophet (Meta) time-series",
            "total_months":   len(records),
            "date_range":     f"{records[0]['month']} to {records[-1]['month']}" if records else "",
            "records":        records,
            "yearly_totals":  yearly_totals,
        }

    except Exception as e:
        data = {
            "source":  "error",
            "error":   str(e),
            "records": [],
            "yearly_totals": [],
            "note": "Run: python pipelines/ingestors/volume_forecast_ingestor.py",
        }

    await set_cache(cache_key, json.dumps(jsonable_encoder(data)), ttl=3600)
    return data


# ── /api/data/report ─────────────────────────────────────────
@router.get("/report")
async def get_report(
    type: str = Query(...),
    from_: str = Query(None, alias="from"),
    to: str = Query(None),
):
    """Trigger Celery async report job — Sprint 6."""
    return {
        "job_id": f"job_placeholder_{type}",
        "status": "queued",
        "type": type,
        "note": "Celery report generation — Sprint 6",
    }


# ── /api/data/admin/* ─────────────────────────────────────────
@router.get("/admin/{path:path}")
async def get_admin(path: str, db: AsyncSession = Depends(get_db)):
    """JWT protected admin routes — Sprint 7."""
    if path.startswith("users"):
        return {"users": [], "note": "JWT auth — Sprint 7"}
    if path.startswith("tables"):
        try:
            result = await db.execute(text(
                "SHOW TABLES"
            ))
            tables = [r[0] for r in result.fetchall()]
            return {"tables": tables}
        except Exception as e:
            return {"tables": [], "error": str(e)}
    return {"error": "not found"}