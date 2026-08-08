r"""
pipelines/ingestors/employment_projections_ingestor.py

Ingests data into `employment_projections` table.
Calculates projection data from `jsa_projected` and `jsa_quarterly_employment`.
"""
import sys
import os
import argparse
import pandas as pd

def configure_console_output():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

configure_console_output()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper
from db.database import sync_engine

def run_ingestor(folder=None, reset=False):
    db_path = settings.DATABASE_URL
    print(f"[DB] Database: {db_path}")
    conn = get_mysql_wrapper(settings)

    print(f"\n{'='*60}")
    print(f"  Employment Projections Ingestor")
    print(f"{'='*60}\n")

    if reset:
        conn.execute("DELETE FROM employment_projections")
        print("  Tabel employment_projections di-reset\n")

    # Ambil employment terkini (average dari 4 quarter terakhir di jsa_quarterly_employment)
    emp_df = pd.read_sql("SELECT anzsco_code, occ_group as sector, employment FROM jsa_quarterly_employment", sync_engine)
    if not emp_df.empty:
        # Untuk simplifikasi, ambil nilai maksimum employment per anzsco_code
        emp_df = emp_df.groupby("anzsco_code").agg({"employment": "max", "sector": "first"}).reset_index()
    else:
        emp_df = pd.DataFrame(columns=["anzsco_code", "employment", "sector"])

    # Ambil projected change dari jsa_projected
    proj_df = pd.read_sql("SELECT anzsco_code, anzsco_name, projected_change, occ_group FROM jsa_projected", sync_engine)
    
    if proj_df.empty:
        print("  Tidak ada data di jsa_projected. Harap jalankan jsa_ingestor.py terlebih dahulu.")
        return

    # Gabungkan data
    df = pd.merge(proj_df, emp_df, on="anzsco_code", how="left")
    
    inserted = 0
    rows = []
    
    for _, r in df.iterrows():
        emp = r.get("employment")
        if pd.isna(emp) or emp is None:
            emp = 0
        else:
            try:
                emp = int(emp)
            except:
                emp = 0
                
        proj_change = str(r.get("projected_change", "0")).replace(',', '').replace('%', '').strip()
        if pd.isna(r.get("projected_change")) or str(r.get("projected_change")).lower() == 'nan':
            proj_change = "0"
        try:
            change_val = float(proj_change)
        except:
            change_val = 0.0
            
        sector = r.get("sector")
        if pd.isna(sector):
            sector = r.get("occ_group", "General")
            
        growth_5yr = change_val
        growth_10yr = growth_5yr * 2  # Estimasi linear jika data 10 tahun tidak tersedia
        
        # Hitung projected employment
        proj_2029 = int(emp * (1 + (growth_5yr / 100)))
        proj_2034 = int(emp * (1 + (growth_10yr / 100)))

        rows.append({
            "anzsco_code": str(r["anzsco_code"]),
            "occupation_name": str(r["anzsco_name"]),
            "employment_2024": int(emp),
            "projected_2029": proj_2029,
            "projected_2034": proj_2034,
            "growth_5yr_pct": growth_5yr,
            "growth_10yr_pct": growth_10yr,
            "sector": str(sector)
        })

    if rows:
        # Hapus data lama agar tidak duplicate jika tidak di reset
        if not reset:
            conn.execute("DELETE FROM employment_projections")
            
        pd.DataFrame(rows).to_sql("employment_projections", sync_engine, if_exists="append", index=False)
        inserted = len(rows)

    print(f"  {inserted:>6,} rows inserted to employment_projections")
    print(f"{'='*60}\n")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default=None, help="Not used for this ingestor as it reads from DB")
    parser.add_argument("--reset", action="store_true", help="Reset tabel dulu")
    args = parser.parse_args()
    run_ingestor(reset=args.reset)
