"""
pipelines/ingestors/migration_grants_ingestor.py

Create migration_grants table from national_migration_quotas
Maps visa stream/category to grants data

Cara pakai:
    python pipelines\\ingestors\\migration_grants_ingestor.py --reset
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS migration_grants (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        financial_year  VARCHAR(10) NOT NULL,
        stream          VARCHAR(50),
        visa_subclass   VARCHAR(10),
        grants          INTEGER,
        planning_level  INTEGER,
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_financial_year (financial_year)
    )
"""

def run_ingestor(reset: bool = False):
    """Create and populate migration_grants table from national_migration_quotas"""
    
    print("\n" + "="*70)
    print("  Migration Grants Ingestor")
    print("  Loading from national_migration_quotas")
    print("="*70 + "\n")
    
    conn = get_mysql_wrapper(settings)
    cur = conn.cursor()
    
    # Step 1: Reset if requested
    if reset:
        print("[1/3] Dropping old table...")
        cur.execute("DROP TABLE IF EXISTS migration_grants")
        conn.commit()
    
    # Step 2: Create table
    print("[2/3] Creating migration_grants table...")
    cur.execute(CREATE_TABLE)
    conn.commit()
    print("      ✓ Table created")
    
    # Step 3: Load data from national_migration_quotas
    print("[3/3] Loading migration grants from quotas...")
    
    # Check if national_migration_quotas has data
    cur.execute("SELECT COUNT(*) FROM national_migration_quotas")
    quota_count = cur.fetchone()[0]
    
    if quota_count == 0:
        print("      ⚠ WARNING: national_migration_quotas table is empty")
        print("      Run quota_ingestor.py first to populate quotas")
        conn.close()
        return
    
    # Map quota stream/category to migration grant categories
    cur.execute("""
        SELECT DISTINCT visa_stream, planning_year FROM national_migration_quotas
        ORDER BY planning_year DESC, visa_stream
    """)
    
    streams = cur.fetchall()
    inserted = 0
    
    for stream, planning_year in streams:
        # Get quota amount
        cur.execute("""
            SELECT SUM(quota_amount) FROM national_migration_quotas
            WHERE visa_stream = %s AND planning_year = %s
        """, (stream, planning_year))
        
        total_quota = cur.fetchone()[0] or 0
        
        # Insert into migration_grants
        # Map planning_year to financial_year (e.g., "2024-25" → "2024-25")
        financial_year = planning_year
        
        # Determine stream name (e.g., "Skilled" for "Skilled - Independent")
        stream_name = stream.split("-")[0].strip() if stream else "Skilled"
        
        cur.execute("""
            INSERT INTO migration_grants
            (financial_year, stream, grants, planning_level)
            VALUES (%s, %s, %s, %s)
        """, (financial_year, stream_name, total_quota, total_quota))
        
        inserted += 1
    
    conn.commit()
    print(f"      ✓ Loaded {inserted:,} migration grant records")
    
    # Verification
    print("\n" + "="*70)
    print("  VERIFICATION")
    print("="*70)
    
    cur.execute("""
        SELECT financial_year, COUNT(*) as count, SUM(grants) as total_grants
        FROM migration_grants
        GROUP BY financial_year
        ORDER BY financial_year DESC
    """)
    
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} streams, {row[2]:,} total grants")
    
    cur.execute("SELECT COUNT(*) FROM migration_grants")
    total = cur.fetchone()[0]
    print(f"\n  Total records: {total:,}")
    
    cur.execute("""
        SELECT stream, COUNT(*) as count, SUM(grants) as total
        FROM migration_grants
        GROUP BY stream
        ORDER BY total DESC
    """)
    
    print(f"\n  By stream:")
    for row in cur.fetchall():
        print(f"    {row[0]:<20} {row[1]:>3} records, {row[2]:>10,} grants")
    
    conn.close()
    
    print("\n" + "="*70)
    print("  ✅ DONE! migration_grants table ready")
    print("="*70 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset table before loading")
    args = parser.parse_args()
    
    run_ingestor(reset=args.reset)
