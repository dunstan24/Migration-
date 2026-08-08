"""
pipelines/ingestors/occupation_features_ingestor.py

Create occupation_features table from eoi_records, jsa_*, and osl_shortage data
Aggregates occupation characteristics for ML model training

Cara pakai:
    python pipelines\\ingestors\\occupation_features_ingestor.py --reset
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS occupation_features (
        id                  INTEGER PRIMARY KEY AUTO_INCREMENT,
        anzsco_code         VARCHAR(6) NOT NULL,
        occupation_name     TEXT,
        state               VARCHAR(5) NOT NULL,
        shortage_count_5yr  INTEGER,
        shortage_streak     INTEGER,
        eoi_pool_size       INTEGER,
        invitation_rate     FLOAT,
        employment_growth   FLOAT,
        jsa_rating          VARCHAR(30),
        pr_probability      FLOAT,
        ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_anzsco_code (anzsco_code),
        INDEX idx_state (state),
        UNIQUE KEY unique_occ_state (anzsco_code, state)
    )
"""

STATES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]

def run_ingestor(reset: bool = False):
    """Create and populate occupation_features table"""
    
    print("\n" + "="*70)
    print("  Occupation Features Ingestor")
    print("  Aggregating features from EOI, JSA, and Shortage data")
    print("="*70 + "\n")
    
    conn = get_mysql_wrapper(settings)
    cur = conn.cursor()
    
    # Step 1: Reset if requested
    if reset:
        print("[1/4] Dropping old table...")
        cur.execute("DROP TABLE IF EXISTS occupation_features")
        conn.commit()
    
    # Step 2: Create table
    print("[2/4] Creating occupation_features table...")
    cur.execute(CREATE_TABLE)
    conn.commit()
    print("      ✓ Table created")
    
    # Step 3: Get unique occupations from eoi_records
    print("[3/4] Extracting occupation features...")
    
    cur.execute("""
        SELECT DISTINCT anzsco_code, occupation_name
        FROM eoi_records
        WHERE anzsco_code IS NOT NULL AND occupation_name IS NOT NULL
        ORDER BY anzsco_code
    """)
    
    occupations = cur.fetchall()
    inserted = 0
    
    for anzsco_code, occupation_name in occupations:
        # Process each state for this occupation
        for state in STATES:
            # Get EOI statistics for this occupation/state
            cur.execute("""
                SELECT 
                    COUNT(*) as pool_size,
                    SUM(CASE WHEN eoi_status = 'INVITED' THEN 1 ELSE 0 END) as invitations,
                    MAX(points) as max_points
                FROM eoi_records
                WHERE anzsco_code = %s AND state = %s
            """, (anzsco_code, state))
            
            eoi_result = cur.fetchone()
            pool_size = eoi_result[0] if eoi_result else 0
            invitations = eoi_result[1] if eoi_result else 0
            invitation_rate = (invitations / pool_size * 100) if pool_size > 0 else 0
            
            # Get shortage history (2021-2025)
            cur.execute("""
                SELECT SUM(CASE WHEN %s = 1 THEN 1 ELSE 0 END) as shortage_years
                FROM osl_shortage
                WHERE anzsco_code = %s AND year >= 2021
            """, (
                "national" if state == "ALL" else state.lower(),
                anzsco_code
            ))
            
            shortage_result = cur.fetchone()
            shortage_count_5yr = shortage_result[0] if shortage_result and shortage_result[0] is not None else 0
            shortage_streak = shortage_count_5yr if shortage_count_5yr > 0 else 0
            
            # Get JSA rating/employment growth (if available)
            cur.execute("""
                SELECT shortage_rating, MAX(projected_change) as emp_growth
                FROM jsa_shortage js
                LEFT JOIN jsa_projected jp ON js.anzsco_code LIKE jp.anzsco_code
                WHERE js.anzsco_code LIKE %s
                LIMIT 1
            """, (anzsco_code[:4] + "%",))
            
            jsa_result = cur.fetchone()
            jsa_rating = jsa_result[0] if jsa_result else None
            emp_growth_raw = jsa_result[1] if jsa_result and jsa_result[1] else 0
            
            # Convert employment_growth to float, handling string/None values
            try:
                employment_growth = float(emp_growth_raw) if emp_growth_raw else 0.0
            except (ValueError, TypeError):
                employment_growth = 0.0
            
            # Calculate PR probability based on shortage and pool size
            # Simple heuristic: higher shortage + smaller pool = higher PR probability
            pr_probability = 0.0
            if shortage_count_5yr >= 3:
                pr_probability += 0.3
            if pool_size < 100:
                pr_probability += 0.2
            if invitation_rate > 50:
                pr_probability += 0.2
            if employment_growth > 0:
                pr_probability += 0.1
            
            pr_probability = min(pr_probability, 1.0)  # Cap at 1.0
            
            # Insert into occupation_features
            cur.execute("""
                INSERT INTO occupation_features
                (anzsco_code, occupation_name, state, shortage_count_5yr, 
                 shortage_streak, eoi_pool_size, invitation_rate, 
                 employment_growth, jsa_rating, pr_probability)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                shortage_count_5yr = VALUES(shortage_count_5yr),
                shortage_streak = VALUES(shortage_streak),
                eoi_pool_size = VALUES(eoi_pool_size),
                invitation_rate = VALUES(invitation_rate),
                employment_growth = VALUES(employment_growth),
                jsa_rating = VALUES(jsa_rating),
                pr_probability = VALUES(pr_probability)
            """, (
                anzsco_code, occupation_name, state, shortage_count_5yr,
                shortage_streak, pool_size, round(invitation_rate, 2),
                employment_growth, jsa_rating, round(pr_probability, 3)
            ))
            
            inserted += 1
    
    conn.commit()
    print(f"      ✓ Loaded {inserted:,} occupation feature records")
    
    # Verification
    print("\n" + "="*70)
    print("  VERIFICATION")
    print("="*70)
    
    cur.execute("""
        SELECT COUNT(DISTINCT anzsco_code) as unique_occupations,
               COUNT(*) as total_records,
               AVG(eoi_pool_size) as avg_pool_size,
               AVG(invitation_rate) as avg_invitation_rate,
               AVG(pr_probability) as avg_pr_prob
        FROM occupation_features
    """)
    
    result = cur.fetchone()
    print(f"  Unique occupations: {result[0]:,}")
    print(f"  Total records:      {result[1]:,}")
    print(f"  Avg EOI pool size:  {result[2]:.0f}")
    print(f"  Avg invitation rate: {result[3]:.1f}%")
    print(f"  Avg PR probability: {result[4]:.3f}")
    
    cur.execute("""
        SELECT state, COUNT(*) as count, AVG(eoi_pool_size) as avg_pool
        FROM occupation_features
        GROUP BY state
        ORDER BY state
    """)
    
    print(f"\n  By state:")
    for row in cur.fetchall():
        print(f"    {row[0]:<5}: {row[1]:>4} occupations, avg pool size {row[2]:.0f}")
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN shortage_count_5yr >= 4 THEN 'High (4-5 years)'
                WHEN shortage_count_5yr >= 2 THEN 'Medium (2-3 years)'
                WHEN shortage_count_5yr >= 1 THEN 'Low (1 year)'
                ELSE 'None'
            END as shortage_level,
            COUNT(*) as count,
            AVG(pr_probability) as avg_pr_prob
        FROM occupation_features
        GROUP BY shortage_count_5yr
        ORDER BY shortage_count_5yr DESC
    """)
    
    print(f"\n  By shortage frequency:")
    for row in cur.fetchall():
        level = row[0] if row[0] else "None"
        print(f"    {level:<25}: {row[1]:>4} records, avg PR prob {row[2]:.3f}")
    
    conn.close()
    
    print("\n" + "="*70)
    print("  ✅ DONE! occupation_features table ready")
    print("="*70 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset table before loading")
    args = parser.parse_args()
    
    run_ingestor(reset=args.reset)
