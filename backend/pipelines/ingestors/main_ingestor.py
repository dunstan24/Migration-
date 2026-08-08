"""
pipelines/ingestors/main_ingestor.py

Main orchestrator untuk menjalankan semua ingestor secara berurutan.

Ingestor yang dijalankan:
    1. EOI Ingestor        - EOI SkillSelect data
    2. JSA Ingestor        - Job Service Australia data
    3. NERO Ingestor       - National Employer Research Office data
    4. NERO SA4 Ingestor   - NERO SA4 regional data
    5. OSL Ingestor        - Online Services Learning data
    6. Quota Ingestor      - Migration quotas
    7. Shortage Forecast   - Occupation shortage forecasts
    8. Volume Forecast     - Volume forecasts
    9. Employment Projections - Employment projections table
   10. Migration Grants     - Migration grants table
   11. Visa Grants         - Visa grants table
   12. Occupation Features - Occupation features table

Cara pakai:
    # Run all ingestors dengan path default
    python main_ingestor.py

    # Run semua ingestor dan reset database
    python main_ingestor.py --reset

    # Run ingestor tertentu saja
    python main_ingestor.py --only eoi,jsa

    # Specify custom data folder
    python main_ingestor.py --data-folder ../../data/raw/
"""

import argparse
import os
import sys
import traceback
from datetime import datetime

# ── Tambah path backend supaya bisa import ingestors ──────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config import settings
from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine

# Import semua ingestor modules
from eoi_ingestor import run_ingestor as run_eoi
from jsa_ingestor import run_ingestor as run_jsa
from nero_ingestor import run_ingestor as run_nero
from nero_sa4_ingestor import run_ingestor as run_nero_sa4
from osl_ingestor import run_ingestor as run_osl
from quota_ingestor import run_ingestor as run_quota
from shortage_forecast_ingestor import run_ingestor as run_shortage
from volume_forecast_ingestor import run_ingestor as run_volume
from shortage_unified_ingestor import run_ingestor as run_shortage_unified
# from employment_projections_ingestor import run_ingestor as run_employment_projections
from migration_grants_ingestor import run_ingestor as run_migration_grants
from visa_grants_ingestor import run_ingestor as run_visa_grants
from occupation_features_ingestor import run_ingestor as run_occupation_features


# ── Define ingestor registry ────────────────────────────────────
INGESTORS = {
    "eoi": {
        "name": "EOI Ingestor",
        "func": run_eoi,
        "folder": "eoi",
        "description": "EOI SkillSelect data"
    },
    "jsa": {
        "name": "JSA Ingestor",
        "func": run_jsa,
        "folder": "jsa",
        "description": "Job Service Australia data"
    },
    "nero": {
        "name": "NERO Ingestor",
        "func": run_nero,
        "folder": "nero",
        "description": "National Employer Research Office data"
    },
    "nero_sa4": {
        "name": "NERO SA4 Ingestor",
        "func": run_nero_sa4,
        "folder": "nero_sa4",
        "description": "NERO SA4 regional data"
    },
    "osl": {
        "name": "OSL Ingestor",
        "func": run_osl,
        "folder": "osl",
        "description": "Online Services Learning data"
    },
    "quota": {
        "name": "Quota Ingestor",
        "func": run_quota,
        "folder": "quota",
        "description": "Migration quotas"
    },
    "shortage": {
        "name": "Shortage Forecast Ingestor",
        "func": run_shortage,
        "folder": "shortage_forecast",
        "description": "Occupation shortage forecasts"
    },
    "volume": {
        "name": "Volume Forecast Ingestor",
        "func": run_volume,
        "folder": "volume_forecast",
        "description": "Volume forecasts"
    },
    "shortage_unified": {
        "name": "Shortage Unified Ingestor",
        "func": run_shortage_unified,
        "folder": None,
        "description": "Unified shortage data (OSL 2021-2025 + Forecast 2026-2030)"
    },
    "migration_grants": {
        "name": "Migration Grants Ingestor",
        "func": run_migration_grants,
        "folder": None,
        "description": "Migration grants data from quotas"
    },
    "visa_grants": {
        "name": "Visa Grants Ingestor",
        "func": run_visa_grants,
        "folder": None,
        "description": "Visa grants data from state quotas"
    },
    "occupation_features": {
        "name": "Occupation Features Ingestor",
        "func": run_occupation_features,
        "folder": None,
        "description": "Occupation features for ML model"
    },
}


def print_header(title):
    """Print formatted header"""
    width = 70
    print("\n" + "=" * width)
    print(f" {title.center(width-2)}")
    print("=" * width)


def print_summary(results):
    """Print execution summary"""
    print_header("EXECUTION SUMMARY")
    
    success_count = sum(1 for k, r in results.items() if not k.startswith("_") and r.get("status") == "SUCCESS")
    failed_count = sum(1 for k, r in results.items() if not k.startswith("_") and r.get("status") == "FAILED")
    skipped_count = sum(1 for k, r in results.items() if not k.startswith("_") and r.get("status") == "SKIPPED")
    
    print(f"\n Timeline:")
    print(f"   Start: {results.get('_start_time', 'N/A')}")
    print(f"   End:   {results.get('_end_time', 'N/A')}")
    
    print(f"\n Statistics:")
    print(f"   [OK] Successful: {success_count}")
    print(f"   [ERR] Failed:     {failed_count}")
    print(f"   [SKIP] Skipped:    {skipped_count}")
    print(f"   Total:        {len(INGESTORS)}")
    
    print(f"\n Details:")
    for name, result in results.items():
        if name.startswith("_"):
            continue
        status_symbol = "[OK]" if result["status"] == "SUCCESS" else "[ERR]" if result["status"] == "FAILED" else "[SKIP]"
        print(f"   {status_symbol} {result['name']:<30} {result['status']}")
        if result.get("error"):
            print(f"      Error: {result['error']}")
    
    print(f"\n Database: {settings.DATABASE_URL}")
    print("=" * 70 + "\n")



def run_all_ingestors(data_folder, reset=False, only=None):
    """
    Run semua ingestor atau yang dispesifikkan dengan `only`.
    
    Args:
        data_folder: Path ke folder berisi raw data
        reset: Jika True, reset database dulu
        only: List nama ingestor yang dijalankan (contoh: ["eoi", "jsa"])
    """
    print_header("MAIN INGESTOR ORCHESTRATOR")
    print(f"\n Configuration:")
    print(f"   Data Folder: {data_folder}")
    print(f"   Database:    {settings.DATABASE_URL}")
    print(f"   Reset DB:    {'YES' if reset else 'NO'}")
    
    if only:
        print(f"   Running:     {', '.join(only)}")
    else:
        print(f"   Running:     ALL INGESTORS")
    
    # -- Initialize database --------------------------------------
    print(f"\n[INIT] Preparing database...")
    db_path = settings.DATABASE_URL
    
    try:
        conn = get_mysql_wrapper(settings)
        
        if reset:
            # Drop all tables if reset
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Disable foreign key checks before dropping
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            conn.commit()
            print(f"   Reset: All tables dropped")
        
        conn.close()
        print(f"   Status: Database ready at {db_path}")
    except Exception as e:
        print(f"   ERROR: Failed to initialize database: {e}")
        raise
    
    results = {
        "_start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    ingestors_to_run = only if only else list(INGESTORS.keys())
    
    for ingestor_key in ingestors_to_run:
        if ingestor_key not in INGESTORS:
            print(f"\n[WARN] Ingestor '{ingestor_key}' tidak ditemukan, skip")
            results[ingestor_key] = {
                "name": ingestor_key,
                "status": "SKIPPED",
                "error": "Not found"
            }
            continue
        
        ingestor = INGESTORS[ingestor_key]
        print(f"\n{'-'*70}")
        print(f" Running: {ingestor['name']}")
        print(f"{'-'*70}")
        
        try:
            # Tentukan folder path untuk ingestor ini (jika diperlukan)
            if ingestor["folder"]:
                ingestor_folder = os.path.join(data_folder, ingestor["folder"])
                
                # Bikin folder jika belum ada (untuk testing)
                os.makedirs(ingestor_folder, exist_ok=True)
                
                print(f"   Folder: {ingestor_folder}\n")
                
                # Jalankan ingestor dengan parameter folder
                ingestor["func"](folder=ingestor_folder, reset=reset)
            else:
                # Ingestor yang tidak memerlukan folder (e.g., dari database tables)
                print(f"   Source: Database tables\n")
                ingestor["func"](reset=reset)
            
            results[ingestor_key] = {
                "name": ingestor["name"],
                "status": "SUCCESS"
            }
            print(f"[OK] {ingestor['name']} completed successfully")
            
        except Exception as e:
            error_msg = str(e)
            print(f"\n[ERR] ERROR in {ingestor['name']}:")
            print(f"   {error_msg}")
            print(f"\n   Full traceback:")
            traceback.print_exc()
            
            results[ingestor_key] = {
                "name": ingestor["name"],
                "status": "FAILED",
                "error": error_msg
            }
    
    results["_end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print_summary(results)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Main orchestrator untuk menjalankan semua ingestor"
    )
    
    parser.add_argument(
        "--data-folder",
        default="../../data/raw",
        help="Path ke folder raw data (default: ../../data/raw)"
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database sebelum ingest"
    )
    
    parser.add_argument(
        "--only",
        type=str,
        help="Jalankan ingestor tertentu saja. Comma-separated list (contoh: eoi,jsa,quota)"
    )
    
    args = parser.parse_args()
    
    # Resolve relative path
    default_base = os.path.dirname(__file__)
    if args.data_folder == "../../data/raw":
        data_folder = os.path.abspath(os.path.join(default_base, "../../data/raw"))
    else:
        data_folder = os.path.abspath(args.data_folder)
    os.makedirs(data_folder, exist_ok=True)
    
    # Parse only list
    only = None
    if args.only:
        only = [x.strip() for x in args.only.split(",")]
    
    # Run
    run_all_ingestors(
        data_folder=data_folder,
        reset=args.reset,
        only=only
    )


if __name__ == "__main__":
    main()