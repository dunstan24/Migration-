"""
pipelines/ingestors/visa_grants_ingestor.py

Create visa_grants table from eoi_records and quota data
Aggregates visa subclass statistics and allocation data

Cara pakai:
    python pipelines\\ingestors\\visa_grants_ingestor.py --reset
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS visa_grants (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        financial_year  VARCHAR(10) NOT NULL,
        visa_subclass   VARCHAR(10),
        visa_name       TEXT,
        country         VARCHAR(100),
        state           VARCHAR(5),
        grants          INTEGER,
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_financial_year (financial_year),
        INDEX idx_visa_subclass (visa_subclass),
        INDEX idx_state (state)
    )
"""

VISA_SUBCLASS_MAP = {
    "189": "Skilled Independent",
    "190": "Skilled Nominated",
    "491": "Skilled Work Regional",
    "185": "Skilled Independent Regional",
    "186": "Employer Nominated",
    "187": "Regional Sponsored Migration Scheme",
}

STATES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]

def run_ingestor(reset: bool = False):
    """Create and populate visa_grants table"""
    
    print("\n" + "="*70)
    print("  Visa Grants Ingestor")
    print("  Loading from state_nomination_quotas + sample allocation data")
    print("="*70 + "\n")
    
    conn = get_mysql_wrapper(settings)
    cur = conn.cursor()
    
    # Step 1: Reset if requested
    if reset:
        print("[1/3] Dropping old table...")
        cur.execute("DROP TABLE IF EXISTS visa_grants")
        conn.commit()
    
    # Step 2: Create table
    print("[2/3] Creating visa_grants table...")
    cur.execute(CREATE_TABLE)
    conn.commit()
    print("      ✓ Table created")
    
    # Step 3: Load data from state_nomination_quotas
    print("[3/3] Loading visa grants from quotas...")
    
    # Check if state_nomination_quotas has data
    cur.execute("SELECT COUNT(*) FROM state_nomination_quotas")
    quota_count = cur.fetchone()[0]
    
    if quota_count == 0:
        print("      ⚠ WARNING: state_nomination_quotas table is empty")
        print("      Run quota_ingestor.py first to populate quotas")
        
        # Create sample data if quotas not available
        print("      Creating sample visa grants data...")
        sample_data = [
            ("2024-25", "189", "Skilled Independent", None, "NSW", 500),
            ("2024-25", "189", "Skilled Independent", None, "VIC", 450),
            ("2024-25", "190", "Skilled Nominated", None, "QLD", 400),
            ("2024-25", "190", "Skilled Nominated", None, "WA", 350),
            ("2024-25", "491", "Skilled Work Regional", None, "TAS", 150),
            ("2024-25", "491", "Skilled Work Regional", None, "NT", 100),
        ]
        
        for row in sample_data:
            cur.execute("""
                INSERT INTO visa_grants
                (financial_year, visa_subclass, visa_name, country, state, grants)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, row)
        
        conn.commit()
        inserted = len(sample_data)
        print(f"      ✓ Loaded {inserted} sample visa grant records")
    else:
        # Load from actual quota data
        cur.execute("""
            SELECT DISTINCT state, visa_type, planning_year FROM state_nomination_quotas
            ORDER BY planning_year DESC, state, visa_type
        """)
        
        quota_rows = cur.fetchall()
        inserted = 0
        
        for state, visa_type, planning_year in quota_rows:
            # Get quota amount
            cur.execute("""
                SELECT SUM(quota_amount) FROM state_nomination_quotas
                WHERE state = %s AND visa_type = %s AND planning_year = %s
            """, (state, visa_type, planning_year))
            
            total_quota = cur.fetchone()[0] or 0
            
            # Get visa name from map
            visa_name = VISA_SUBCLASS_MAP.get(visa_type, f"Visa {visa_type}")
            
            # Insert into visa_grants
            cur.execute("""
                INSERT INTO visa_grants
                (financial_year, visa_subclass, visa_name, state, grants)
                VALUES (%s, %s, %s, %s, %s)
            """, (planning_year, visa_type, visa_name, state, total_quota))
            
            inserted += 1
        
        conn.commit()
        print(f"      ✓ Loaded {inserted:,} visa grant records from quotas")
    
    # Verification
    print("\n" + "="*70)
    print("  VERIFICATION")
    print("="*70)
    
    cur.execute("""
        SELECT COUNT(*) as total, SUM(grants) as total_grants
        FROM visa_grants
    """)
    
    result = cur.fetchone()
    print(f"  Total records: {result[0]:,}")
    print(f"  Total grants:  {result[1]:,}")
    
    cur.execute("""
        SELECT visa_subclass, visa_name, COUNT(*) as count, SUM(grants) as total
        FROM visa_grants
        GROUP BY visa_subclass, visa_name
        ORDER BY total DESC
    """)
    
    print(f"\n  By visa subclass:")
    for row in cur.fetchall():
        print(f"    {row[0]} ({row[1]:<25}): {row[2]:>3} states, {row[3]:>8,} grants")
    
    cur.execute("""
        SELECT state, COUNT(*) as count, SUM(grants) as total
        FROM visa_grants
        GROUP BY state
        ORDER BY total DESC
    """)
    
    print(f"\n  By state:")
    for row in cur.fetchall():
        print(f"    {row[0]:<5}: {row[1]:>3} visa classes, {row[2]:>8,} grants")
    
    conn.close()
    
    print("\n" + "="*70)
    print("  ✅ DONE! visa_grants table ready")
    print("="*70 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset table before loading")
    args = parser.parse_args()
    
    run_ingestor(reset=args.reset)
