"""
pipelines/ingestors/nero_ingestor.pywwwwww

Membaca NERO (Non-Employer Reported Online job ads) data untuk
Regional dan Northern Australia → warehouse.db

File yang dibutuhkan di folder:
    YYYY_MM_regional.csv            → NERO per ANZSCO4, Regional vs Major City
    YYYY_MM_northern_australia.csv  → NERO per ANZSCO4, Northern Australia
    JSA_Regional_Classification.xlsx → SA4 mapping

Tabel yang dibuat:
    nero_regional    → time series NERO per ANZSCO4, regional/major city
    nero_northern    → time series NERO per ANZSCO4, northern australia
    nero_sa4_lookup  → SA4 code → remoteness + northern australia flag

Cara pakai:
    python pipelines\\ingestors\\nero_ingestor.py --folder data\\raw\\nero\\ --reset
"""
import argparse
import pandas as pd
import os
import sys
import glob
import re
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper
from db.database import sync_engine

# ── Table definitions (MySQL syntax only) ─────────────────────────────
CREATE_REGIONAL = """
    CREATE TABLE IF NOT EXISTS nero_regional (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        anzsco4_code    INTEGER NOT NULL,
        anzsco4_name    VARCHAR(255) NOT NULL,
        date            VARCHAR(20) NOT NULL,
        year            INTEGER NOT NULL,
        month           INTEGER NOT NULL,
        jsa_remoteness  VARCHAR(100) NOT NULL,
        nero_estimate   INTEGER NOT NULL,
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_NORTHERN = """
    CREATE TABLE IF NOT EXISTS nero_northern (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        anzsco4_code    INTEGER NOT NULL,
        anzsco4_name    VARCHAR(255) NOT NULL,
        date            VARCHAR(20) NOT NULL,
        year            INTEGER NOT NULL,
        month           INTEGER NOT NULL,
        northern_australia VARCHAR(100) NOT NULL,
        nero_estimate   INTEGER NOT NULL,
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_SA4 = """
    CREATE TABLE IF NOT EXISTS nero_sa4_lookup (
        id                  INTEGER PRIMARY KEY AUTO_INCREMENT,
        sa4_code            INTEGER NOT NULL,
        sa4_name            VARCHAR(255) NOT NULL,
        jsa_remoteness      VARCHAR(100),
        northern_australia  VARCHAR(100),
        ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_nero_reg_anzsco  ON nero_regional(anzsco4_code)",
    "CREATE INDEX IF NOT EXISTS idx_nero_reg_date    ON nero_regional(date)",
    "CREATE INDEX IF NOT EXISTS idx_nero_reg_yr_mo   ON nero_regional(year, month)",
    "CREATE INDEX IF NOT EXISTS idx_nero_reg_remote  ON nero_regional(jsa_remoteness)",
    "CREATE INDEX IF NOT EXISTS idx_nero_nth_anzsco  ON nero_northern(anzsco4_code)",
    "CREATE INDEX IF NOT EXISTS idx_nero_nth_date    ON nero_northern(date)",
    "CREATE INDEX IF NOT EXISTS idx_nero_nth_yr_mo   ON nero_northern(year, month)",
]


def parse_date(date_str):
    """Parse M/D/YYYY or YYYY-MM-DD → (YYYY-MM-DD, year, month)"""
    ds = str(date_str).strip()
    for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(ds, fmt)
            return dt.strftime("%Y-%m-%d"), dt.year, dt.month
        except:
            continue
    return ds, 0, 0


def find_file(folder, pattern_keywords):
    """Find file in folder matching any keyword in list."""
    all_files = glob.glob(os.path.join(folder, "*.csv")) + \
                glob.glob(os.path.join(folder, "*.xlsx"))
    for f in all_files:
        fname = os.path.basename(f).lower()
        if all(kw.lower() in fname for kw in pattern_keywords):
            return f
    return None


def ingest_regional(filepath, conn):
    print(f"\n  Reading: {os.path.basename(filepath)}")
    df = pd.read_csv(filepath)
    print(f"  Shape: {df.shape}")

    rows = []
    for _, r in df.iterrows():
        date_str, year, month = parse_date(r['date'])
        rows.append((
            int(r['anzsco4_code']),
            str(r['anzsco4_name']).strip(),
            date_str, year, month,
            str(r['jsa_remoteness']).strip(),
            int(r['nero_estimate']),
        ))

    conn.executemany("""
        INSERT INTO nero_regional
        (anzsco4_code, anzsco4_name, date, year, month, jsa_remoteness, nero_estimate)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, rows)
    conn.commit()
    print(f"  Inserted {len(rows):,} rows into nero_regional")

    # Show date range
    years = sorted(set(r[3] for r in rows))
    print(f"  Date range: {years[0]} → {years[-1]}")
    print(f"  ANZSCO4 codes: {len(set(r[0] for r in rows))}")
    print(f"  Remoteness: {set(r[5] for r in rows)}")
    return len(rows)


def ingest_northern(filepath, conn):
    print(f"\n  Reading: {os.path.basename(filepath)}")
    df = pd.read_csv(filepath)
    print(f"  Shape: {df.shape}")

    rows = []
    for _, r in df.iterrows():
        date_str, year, month = parse_date(r['date'])
        rows.append((
            int(r['anzsco4_code']),
            str(r['anzsco4_name']).strip(),
            date_str, year, month,
            str(r['northern_australia']).strip(),
            int(r['nero_estimate']),
        ))

    conn.executemany("""
        INSERT INTO nero_northern
        (anzsco4_code, anzsco4_name, date, year, month, northern_australia, nero_estimate)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, rows)
    conn.commit()
    print(f"  Inserted {len(rows):,} rows into nero_northern")

    years = sorted(set(r[3] for r in rows))
    print(f"  Date range: {years[0]} → {years[-1]}")
    return len(rows)


def ingest_sa4(filepath, conn):
    print(f"\n  Reading: {os.path.basename(filepath)}")
    df = pd.read_excel(filepath)
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {df.columns.tolist()}")

    # Detect columns flexibly
    col_sa4_code = next((c for c in df.columns if "code" in str(c).lower()), df.columns[0])
    col_sa4_name = next((c for c in df.columns if "name" in str(c).lower()), df.columns[1])
    col_remote   = next((c for c in df.columns if "remote" in str(c).lower()), df.columns[2])
    col_northern = next((c for c in df.columns if "northern" in str(c).lower()), df.columns[3])

    rows = []
    for _, r in df.iterrows():
        if pd.isna(r[col_sa4_code]):
            continue
        rows.append((
            int(r[col_sa4_code]),
            str(r[col_sa4_name]).strip(),
            str(r[col_remote]).strip() if pd.notna(r[col_remote]) else "",
            str(r[col_northern]).strip() if pd.notna(r[col_northern]) else "",
        ))

    conn.executemany("""
        INSERT INTO nero_sa4_lookup
        (sa4_code, sa4_name, jsa_remoteness, northern_australia)
        VALUES (%s,%s,%s,%s)
    """, rows)
    conn.commit()
    print(f"  Inserted {len(rows):,} rows into nero_sa4_lookup")
    return len(rows)


def run_ingestor(folder, reset=False):
    db_path = settings.DATABASE_URL
    conn = get_mysql_wrapper(settings)

    print(f"\n{'='*57}")
    print(f"  NERO Ingestor — Regional & Northern Australia")
    print(f"  Folder  : {folder}")
    print(f"  Database: {db_path}")
    print(f"{'='*57}")

    if reset:
        for tbl in ["nero_regional", "nero_northern", "nero_sa4_lookup"]:
            conn.execute(f"DROP TABLE IF EXISTS {tbl}")
        print("\n  Tabel NERO di-reset")

    for sql in [CREATE_REGIONAL, CREATE_NORTHERN, CREATE_SA4]:
        conn.execute(sql)
    for idx in INDEXES:
        conn.execute(idx)
    conn.commit()
    print("\n  Tabel siap:")
    print("    - nero_regional")
    print("    - nero_northern")
    print("    - nero_sa4_lookup")

    total = 0

    # Find regional file — matches *regional*.csv
    reg_file = find_file(folder, ["regional"])
    if not reg_file:
        # Try any CSV that isn't northern
        csvs = glob.glob(os.path.join(folder, "*.csv"))
        reg_file = next((f for f in csvs if "northern" not in f.lower()), None)
    if reg_file:
        total += ingest_regional(reg_file, conn)
    else:
        print("\n  WARNING: regional CSV tidak ditemukan")

    # Find northern file
    nth_file = find_file(folder, ["northern"])
    if nth_file:
        total += ingest_northern(nth_file, conn)
    else:
        print("\n  WARNING: northern_australia CSV tidak ditemukan")

    # Find SA4 classification file
    sa4_file = find_file(folder, ["classification"])
    if not sa4_file:
        sa4_file = find_file(folder, ["regional_classification"])
    if not sa4_file:
        xlsx = glob.glob(os.path.join(folder, "*.xlsx"))
        sa4_file = xlsx[0] if xlsx else None
    if sa4_file:
        total += ingest_sa4(sa4_file, conn)
    else:
        print("\n  WARNING: JSA_Regional_Classification.xlsx tidak ditemukan")

    # Summary
    print(f"\n{'='*57}")
    print(f"  Selesai! Total: {total:,} rows")
    print(f"\n  Rows per tabel:")
    for tbl in ["nero_regional", "nero_northern", "nero_sa4_lookup"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"    {tbl:<25} {count:>8,} rows")
        except Exception as e:
            print(f"    {tbl:<25} ERROR: {e}")

    # NERO sample — top 5 occupations by latest regional NERO
    print(f"\n  Top 5 occupations by NERO (latest Regional):")
    try:
        latest = conn.execute("SELECT MAX(date) FROM nero_regional").fetchone()[0]
        rows = conn.execute(f"""
            SELECT anzsco4_code, anzsco4_name, jsa_remoteness, nero_estimate
            FROM nero_regional WHERE date = '{latest}'
            ORDER BY nero_estimate DESC LIMIT 10
        """).fetchall()
        for r in rows:
            print(f"    {r[0]} | {r[1][:35]:<35} | {r[2]:<10} | {r[3]:>8,}")
    except Exception as e:
        print(f"    ERROR: {e}")

    print(f"{'='*57}\n")
    conn.close()


if __name__ == "__main__":
    default_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw/nero"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder",
        default=default_folder,
        help=f"Folder berisi file NERO CSV + xlsx (default: {default_folder})",
    )
    parser.add_argument("--reset", action="store_true", help="Reset tabel dulu")
    args = parser.parse_args()
    run_ingestor(folder=args.folder, reset=args.reset)