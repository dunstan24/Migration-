"""
pipelines/ingestors/quota_ingestor.py

Membaca file quota Excel → MySQL database
File yang dibutuhkan:
    - national_migration_quotas.xlsx
    - state_nomination_allocations.xlsx

Tabel yang dibuat:
    national_migration_quotas   → planning levels per visa stream per tahun
    state_nomination_quotas     → alokasi slot per state per visa type

Cara pakai:
    python pipelines\\ingestors\\quota_ingestor.py --folder data\\raw\\quota\\ --reset
"""
import argparse
import pandas as pd
import os
import sys
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper

CREATE_NATIONAL = """
    CREATE TABLE IF NOT EXISTS national_migration_quotas (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        visa_stream     VARCHAR(100) NOT NULL,
        visa_category   VARCHAR(100) NOT NULL,
        planning_year   VARCHAR(20) NOT NULL,
        quota_amount    INTEGER,
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_STATE = """
    CREATE TABLE IF NOT EXISTS state_nomination_quotas (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        state           VARCHAR(50) NOT NULL,
        visa_type       VARCHAR(10) NOT NULL,
        quota_amount    INTEGER NOT NULL,
        planning_year   VARCHAR(20) NOT NULL,
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_natquota_year     ON national_migration_quotas(planning_year)",
    "CREATE INDEX IF NOT EXISTS idx_natquota_stream   ON national_migration_quotas(visa_stream)",
    "CREATE INDEX IF NOT EXISTS idx_stquota_state     ON state_nomination_quotas(state)",
    "CREATE INDEX IF NOT EXISTS idx_stquota_year      ON state_nomination_quotas(planning_year)",
    "CREATE INDEX IF NOT EXISTS idx_stquota_visa      ON state_nomination_quotas(visa_type)",
]


def safe_int(val):
    """Convert value to int, return None if dash or NaN."""
    if pd.isna(val):
        return None
    s = str(val).strip().replace(",", "")
    if s in ("-", "", "–", "—"):
        return None
    try:
        return int(float(s))
    except:
        return None


def ingest_national(filepath, conn):
    """Ingest national_migration_quotas.xlsx"""
    print(f"\n  Reading: {os.path.basename(filepath)}")
    df = pd.read_excel(filepath)

    # Detect year columns (columns containing planning levels)
    year_cols = [c for c in df.columns if "Planning" in str(c) or "planning" in str(c) or "20" in str(c)]
    print(f"  Year columns detected: {year_cols}")

    rows = []
    for _, r in df.iterrows():
        stream   = str(r.iloc[0]).strip() if pd.notna(r.iloc[0]) else ""
        category = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""

        if not stream or not category:
            continue

        for col in year_cols:
            year_label = str(col).strip()
            # Extract year range e.g. "2023–24 Planning levels" → "2023-24"
            year_label = year_label.replace("Planning levels", "").replace("planning levels", "").strip()
            year_label = year_label.replace("–", "-").strip()

            amount = safe_int(r[col])
            rows.append((stream, category, year_label, amount))

    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO national_migration_quotas
        (visa_stream, visa_category, planning_year, quota_amount)
        VALUES (%s,%s,%s,%s)
    """, rows)
    conn.commit()
    print(f"  Inserted {len(rows)} rows into national_migration_quotas")
    return len(rows)


def ingest_state(filepath, conn):
    """Ingest state_nomination_allocations.xlsx"""
    print(f"\n  Reading: {os.path.basename(filepath)}")
    df = pd.read_excel(filepath)

    # Detect visa columns
    visa_cols = {}
    for col in df.columns:
        col_str = str(col).lower()
        if "190" in col_str:
            visa_cols["190"] = col
        elif "491" in col_str:
            visa_cols["491"] = col

    print(f"  Visa columns detected: {visa_cols}")

    # Detect planning year from column names
    planning_year = "2024-25"  # default
    for col in df.columns:
        col_str = str(col)
        if "20" in col_str and "-" in col_str:
            import re
            match = re.search(r'(20\d{2}[-–]\d{2})', col_str)
            if match:
                planning_year = match.group(1).replace("–", "-")
                break

    print(f"  Planning year: {planning_year}")

    # Skip subtotal/total rows
    skip_keywords = ["sub total", "subtotal", "total"]

    rows = []
    for _, r in df.iterrows():
        state = str(r.iloc[0]).strip() if pd.notna(r.iloc[0]) else ""
        if not state or state.lower() in skip_keywords:
            continue

        for visa_type, col in visa_cols.items():
            amount = safe_int(r[col])
            if amount is not None:
                rows.append((state, visa_type, amount, planning_year))

    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO state_nomination_quotas
        (state, visa_type, quota_amount, planning_year)
        VALUES (%s,%s,%s,%s)
    """, rows)
    conn.commit()
    print(f"  Inserted {len(rows)} rows into state_nomination_quotas")
    return len(rows)


def run_ingestor(folder, reset=False):
    conn = get_mysql_wrapper(settings)
    cur = conn.cursor()

    print(f"\n{'='*55}")
    print(f"  Quota Ingestor")
    print(f"  Folder  : {folder}")
    print(f"  Database: MySQL")
    print(f"{'='*55}")

    if reset:
        cur.execute("DROP TABLE IF EXISTS national_migration_quotas")
        cur.execute("DROP TABLE IF EXISTS state_nomination_quotas")
        conn.commit()
        print("\n  Tabel quota di-reset")

    cur.execute(CREATE_NATIONAL)
    cur.execute(CREATE_STATE)
    for idx in INDEXES:
        cur.execute(idx)
    conn.commit()
    print("\n  Tabel siap:")
    print("    - national_migration_quotas")
    print("    - state_nomination_quotas")

    total = 0

    # Find national quotas file
    nat_files = glob.glob(os.path.join(folder, "*national*migration*quota*.xlsx")) + \
                glob.glob(os.path.join(folder, "*national*.xlsx"))
    if nat_files:
        total += ingest_national(nat_files[0], conn)
    else:
        print("\n  WARNING: national_migration_quotas.xlsx tidak ditemukan")
        print("           Pastikan nama file mengandung kata 'national'")

    # Find state quotas file
    state_files = glob.glob(os.path.join(folder, "*state*nomination*.xlsx")) + \
                  glob.glob(os.path.join(folder, "*state*.xlsx"))
    # Exclude national file from state results
    state_files = [f for f in state_files if "national" not in os.path.basename(f).lower()]
    if state_files:
        total += ingest_state(state_files[0], conn)
    else:
        print("\n  WARNING: state_nomination_allocations.xlsx tidak ditemukan")
        print("           Pastikan nama file mengandung kata 'state'")

    # Summary
    print(f"\n{'='*55}")
    print(f"  Selesai! Total: {total:,} rows")
    print(f"\n  Rows per tabel:")
    for tbl in ["national_migration_quotas", "state_nomination_quotas"]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            count = cur.fetchone()[0]
            print(f"    {tbl:<35} {count:>6} rows")
        except Exception as e:
            print(f"    {tbl:<35} ERROR: {e}")

    # Preview state quotas
    print(f"\n  State quota preview:")
    try:
        cur.execute("""
            SELECT state, visa_type, quota_amount, planning_year
            FROM state_nomination_quotas
            ORDER BY visa_type, quota_amount DESC
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"    {r[3]} | {r[0]:<5} Visa {r[1]}: {r[2]:,}")
    except:
        pass

    print(f"{'='*55}\n")
    conn.close()


if __name__ == "__main__":
    default_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw/quota"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder",
        default=default_folder,
        help=f"Folder berisi file quota xlsx (default: {default_folder})",
    )
    parser.add_argument("--reset", action="store_true", help="Reset tabel dulu")
    args = parser.parse_args()
    run_ingestor(folder=args.folder, reset=args.reset)