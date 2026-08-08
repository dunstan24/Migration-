#!/usr/bin/env python
"""
validate_mysql_ingestors.py

Quick validation script to check MySQL connection and run data ingestion
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from db.mysql_wrapper import get_mysql_wrapper

def test_mysql_connection():
    """Test MySQL connection"""
    print("\n" + "="*70)
    print("  MYSQL CONNECTION TEST")
    print("="*70)
    
    try:
        conn = get_mysql_wrapper(settings)
        cur = conn.cursor()
        
        # Simple query to verify connection
        cur.execute("SELECT VERSION()")
        version = cur.fetchone()[0]
        print(f"  ✅ MySQL connection successful")
        print(f"  Version: {version}")
        
        # Show database
        cur.execute("SELECT DATABASE()")
        db_name = cur.fetchone()[0]
        print(f"  Database: {db_name}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ MySQL connection failed")
        print(f"  Error: {e}")
        return False

def check_existing_tables():
    """Check which tables exist and have data"""
    print("\n" + "="*70)
    print("  EXISTING TABLES")
    print("="*70)
    
    tables_to_check = [
        "eoi_records",
        "jsa_shortage",
        "jsa_projected",
        "nero_regional",
        "nero_sa4",
        "osl_shortage",
        "shortage_forecast",
        "national_migration_quotas",
        "state_nomination_quotas",
        "migration_grants",
        "visa_grants",
        "occupation_features",
        "shortage_unified",
    ]
    
    try:
        conn = get_mysql_wrapper(settings)
        cur = conn.cursor()
        
        print(f"\n  {'Table':<35} {'Exists':<10} {'Records'}")
        print(f"  {'-'*70}")
        
        for table in tables_to_check:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                status = "✅ YES" if count > 0 else "⚠ EMPTY"
                print(f"  {table:<35} {status:<10} {count:,}")
            except:
                print(f"  {table:<35} {'❌ NO':<10} -")
        
        conn.close()
    except Exception as e:
        print(f"  Error checking tables: {e}")

def show_ingestor_order():
    """Show recommended ingestor execution order"""
    print("\n" + "="*70)
    print("  RECOMMENDED INGESTOR EXECUTION ORDER")
    print("="*70)
    
    ingestors = [
        ("1. eoi", "python pipelines/ingestors/eoi_ingestor.py --folder backend/data/raw/eoi", "Prerequisites for occupation_features"),
        ("2. jsa", "python pipelines/ingestors/jsa_ingestor.py --folder backend/data/raw/jsa", "Prerequisites for occupation_features"),
        ("3. osl", "python pipelines/ingestors/osl_ingestor.py --folder backend/data/raw/osl", "Prerequisites for shortage_unified"),
        ("4. shortage_forecast", "python pipelines/ingestors/shortage_forecast_ingestor.py --folder backend/data/raw/shortage_forecast", "Prerequisites for shortage_unified"),
        ("5. shortage_unified", "python pipelines/ingestors/shortage_unified_ingestor.py", "Combine OSL + Forecast"),
        ("6. quota", "python pipelines/ingestors/quota_ingestor.py --folder backend/data/raw/quota", "Prerequisites for migration_grants + visa_grants"),
        ("7. migration_grants", "python pipelines/ingestors/migration_grants_ingestor.py", "From quota data"),
        ("8. visa_grants", "python pipelines/ingestors/visa_grants_ingestor.py", "From quota data"),
        ("9. occupation_features", "python pipelines/ingestors/occupation_features_ingestor.py", "From EOI + JSA data"),
    ]
    
    for name, cmd, notes in ingestors:
        print(f"\n  {name}")
        print(f"    Command: {cmd}")
        print(f"    Notes:   {notes}")

def main():
    """Run validation suite"""
    print("\n" + "="*70)
    print("  MYSQL INGESTORS VALIDATION SUITE")
    print("="*70)
    
    # Test connection
    if not test_mysql_connection():
        print("\n❌ Cannot proceed without MySQL connection!")
        print("   Please check your DATABASE_URL environment variable")
        sys.exit(1)
    
    # Check existing tables
    check_existing_tables()
    
    # Show ingestor order
    show_ingestor_order()
    
    print("\n" + "="*70)
    print("  NEXT STEPS")
    print("="*70)
    print("""
  1. Navigate to the backend folder:
     cd backend

  2. Run ingestors in order (fastest first):
     python pipelines/ingestors/osl_ingestor.py --folder data/raw/osl
     python pipelines/ingestors/shortage_forecast_ingestor.py --folder data/raw/shortage_forecast
     python pipelines/ingestors/shortage_unified_ingestor.py
     python pipelines/ingestors/quota_ingestor.py --folder data/raw/quota
     python pipelines/ingestors/migration_grants_ingestor.py
     python pipelines/ingestors/visa_grants_ingestor.py
     python pipelines/ingestors/occupation_features_ingestor.py

  3. Verify tables are populated:
     python validate_mysql_ingestors.py

  💡 Tip: Run main_ingestor.py to execute all at once:
     python pipelines/ingestors/main_ingestor.py --reset
    """)
    
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
