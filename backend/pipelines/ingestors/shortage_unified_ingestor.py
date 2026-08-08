"""
pipelines/ingestors/shortage_unified_ingestor.py

Create unified shortage table from:
  1. OSL Shortage (2021-2025) — unpivoted to long format
  2. Shortage Forecast (2026-2030) — from ML model

Cara pakai:
    python pipelines\\ingestors\\shortage_unified_ingestor.py --reset
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper

STATES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS shortage_unified (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        anzsco_code     VARCHAR(6) NOT NULL,
        occupation_name TEXT NOT NULL,
        skill_level     INTEGER,
        year            INTEGER NOT NULL,
        state           VARCHAR(5) NOT NULL,
        is_shortage     INTEGER,
        prob_shortage   FLOAT,
        source          VARCHAR(20),
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_code_state_year (anzsco_code, state, year),
        INDEX idx_code (anzsco_code),
        INDEX idx_year (year),
        INDEX idx_state (state),
        INDEX idx_source (source),
        INDEX idx_prob (prob_shortage DESC)
    )
"""

def run_ingestor(reset: bool = False):
    """Create and populate shortage_unified table"""
    
    print("\n" + "="*70)
    print("  INTERLACE — Shortage Unified Ingestor")
    print("  Loading OSL (2021-2025) + Forecast (2026-2030)")
    print("="*70 + "\n")
    
    conn = get_mysql_wrapper(settings)
    cur = conn.cursor()
    
    # Step 1: Reset if requested
    if reset:
        print("[1/4] Dropping old table...")
        cur.execute("DROP TABLE IF EXISTS shortage_unified")
        conn.commit()
    
    # Step 2: Create table
    print("[2/4] Creating shortage_unified table...")
    cur.execute(CREATE_TABLE)
    conn.commit()
    print("      ✓ Table created")
    
    # Step 3: Load OSL data (unpivoted)
    print("[3/4] Loading OSL shortage data (2021-2025)...")
    cur.execute("""
        SELECT year, anzsco_code, occupation_name, skill_level, 
               nsw, vic, qld, sa, wa, tas, nt, act
        FROM osl_shortage
        WHERE year >= 2021 AND occupation_name != ''
        ORDER BY year DESC
    """)
    
    osl_rows = cur.fetchall()
    osl_inserted = 0
    
    for row in osl_rows:
        year, code, occ_name, skill_level = row[0], row[1], row[2], row[3]
        state_vals = row[4:]  # nsw, vic, qld, sa, wa, tas, nt, act
        
        for state_idx, state_name in enumerate(STATES):
            is_shortage = state_vals[state_idx]
            
            cur.execute("""
                INSERT INTO shortage_unified
                (anzsco_code, occupation_name, skill_level, year, state, 
                 is_shortage, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                is_shortage = VALUES(is_shortage),
                source = 'osl'
            """, (code, occ_name, skill_level, year, state_name, is_shortage, 'osl'))
            osl_inserted += 1
    
    conn.commit()
    print(f"      ✓ Loaded {osl_inserted:,} OSL records (unpivoted)")
    
    # Step 4: Load Forecast data (2026-2030)
    print("[4/4] Loading shortage forecast data (2026-2030)...")
    cur.execute("""
        SELECT anzsco_code, occupation, state,
               prob_2026, prob_2027, prob_2028, prob_2029, prob_2030
        FROM shortage_forecast
        WHERE occupation != ''
    """)
    
    forecast_rows = cur.fetchall()
    forecast_inserted = 0
    
    for row in forecast_rows:
        code, occ, state = row[0], row[1], row[2]
        probs = row[3:8]  # prob_2026, ..., prob_2030
        
        for year_offset, prob in enumerate(probs):
            year = 2026 + year_offset
            
            cur.execute("""
                INSERT INTO shortage_unified
                (anzsco_code, occupation_name, year, state, prob_shortage, source)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                prob_shortage = VALUES(prob_shortage),
                source = CASE 
                    WHEN source = 'osl' THEN 'osl+forecast'
                    ELSE 'forecast'
                END
            """, (code, occ, year, state, prob, 'forecast'))
            forecast_inserted += 1
    
    conn.commit()
    print(f"      ✓ Loaded {forecast_inserted:,} forecast records")
    
    # Verification
    print("\n" + "="*70)
    print("  VERIFICATION")
    print("="*70)
    
    cur.execute("""
        SELECT source, COUNT(*) as cnt, COUNT(DISTINCT anzsco_code) as codes
        FROM shortage_unified
        GROUP BY source
    """)
    for src_row in cur.fetchall():
        print(f"  {src_row[0]:<10}: {src_row[1]:>8,} records | {src_row[2]:>6,} unique codes")
    
    cur.execute("SELECT COUNT(*) FROM shortage_unified")
    total = cur.fetchone()[0]
    print(f"  {'TOTAL':<10}: {total:>8,} records")
    
    cur.execute("""
        SELECT year, COUNT(*) FROM shortage_unified GROUP BY year ORDER BY year DESC LIMIT 5
    """)
    print(f"\n  Top 5 years:")
    for yr_row in cur.fetchall():
        print(f"    {yr_row[0]}: {yr_row[1]:,} records")
    
    cur.execute("""
        SELECT state, COUNT(*) FROM shortage_unified GROUP BY state ORDER BY COUNT(*) DESC
    """)
    print(f"\n  By state:")
    for st_row in cur.fetchall():
        print(f"    {st_row[0]}: {st_row[1]:,} records")
    
    conn.close()
    
    print("\n" + "="*70)
    print("  ✅ DONE! shortage_unified table ready")
    print("="*70 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset table before loading")
    args = parser.parse_args()
    
    run_ingestor(reset=args.reset)
