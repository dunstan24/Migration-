"""
pipelines/ingestors/nero_sa4_ingestor.py

Membaca file NERO SA4-level (CSV atau XLSX) → warehouse.db
Format kolom: state_name, sa4_code, sa4_name, anzsco4_code, anzsco4_name, date, nsc_emp

Mendukung:
  - File tunggal (--file)
  - Seluruh folder sekaligus (--folder) — proses semua .csv dan .xlsx

NSW dibagi 2 file (Part 1 & Part 2) — keduanya akan di-append otomatis.

Cara pakai:
    # Satu folder (recommended):
    python pipelines\ingestors\nero_sa4_ingestor.py --folder data\raw\nero_sa4\ --reset

    # File tunggal:
    python pipelines\ingestors\nero_sa4_ingestor.py --file data\raw\nero_sa4\2026-02_shiny_df_NT.xlsx
"""
import argparse
import pandas as pd
import os
import sys
import glob
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper

CHUNK_SIZE = 50_000

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS nero_sa4 (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        state_name      VARCHAR(100) NOT NULL,
        sa4_code        INTEGER NOT NULL,
        sa4_name        VARCHAR(200) NOT NULL,
        anzsco4_code    INTEGER NOT NULL,
        anzsco4_name    VARCHAR(200) NOT NULL,
        date            VARCHAR(20) NOT NULL,
        year            INTEGER NOT NULL,
        month           INTEGER NOT NULL,
        nsc_emp         INTEGER,
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_nero_sa4_anzsco      ON nero_sa4(anzsco4_code)",
    "CREATE INDEX IF NOT EXISTS idx_nero_sa4_sa4code     ON nero_sa4(sa4_code)",
    "CREATE INDEX IF NOT EXISTS idx_nero_sa4_state       ON nero_sa4(state_name)",
    "CREATE INDEX IF NOT EXISTS idx_nero_sa4_date        ON nero_sa4(date)",
    "CREATE INDEX IF NOT EXISTS idx_nero_sa4_yr_mo       ON nero_sa4(year, month)",
    "CREATE INDEX IF NOT EXISTS idx_nero_sa4_anzsco_date ON nero_sa4(anzsco4_code, date)",
    "CREATE INDEX IF NOT EXISTS idx_nero_sa4_state_date  ON nero_sa4(state_name, date)",
]


def parse_date(date_str):
    s = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d"), dt.year, dt.month
        except:
            continue
    return s, 0, 0


def detect_columns(df):
    cols = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    mapping = {}
    for key, candidates in {
        "state_name":   ["state_name", "state"],
        "sa4_code":     ["sa4_code", "sa4code"],
        "sa4_name":     ["sa4_name", "sa4name"],
        "anzsco4_code": ["anzsco4_code", "anzsco4", "anzsco_code"],
        "anzsco4_name": ["anzsco4_name", "anzsco4name", "anzsco_name"],
        "date":         ["date"],
        "nsc_emp":      ["nsc_emp", "nero_estimate", "employment", "emp"],
    }.items():
        for c in candidates:
            if c in cols:
                mapping[key] = cols[c]
                break
    return mapping


def ingest_file(filepath, conn, file_num=1, total_files=1):
    fname = os.path.basename(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    size_mb = os.path.getsize(filepath) / 1024 / 1024

    print(f"\n  [{file_num}/{total_files}] {fname}  ({size_mb:.1f} MB)")

    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
        df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
        chunks = [df[i:i+CHUNK_SIZE] for i in range(0, len(df), CHUNK_SIZE)]
    else:
        chunks = list(pd.read_csv(filepath, chunksize=CHUNK_SIZE, low_memory=False))

    col_map = detect_columns(chunks[0])
    missing = [k for k in ["state_name","sa4_code","sa4_name","anzsco4_code","anzsco4_name","date","nsc_emp"]
               if k not in col_map]
    if missing:
        print(f"  WARNING: Kolom tidak ditemukan: {missing}")
        print(f"  Kolom tersedia: {chunks[0].columns.tolist()}")
        return 0

    state = str(chunks[0][col_map["state_name"]].iloc[0]) if len(chunks[0]) > 0 else "?"
    total = 0
    skipped = 0
    start = time.time()

    for chunk in chunks:
        chunk = chunk.loc[:, ~chunk.columns.str.startswith("Unnamed")]
        rows = []
        for _, r in chunk.iterrows():
            try:
                date_str, year, month = parse_date(r[col_map["date"]])
                nsc_val = r[col_map["nsc_emp"]]
                nsc_emp = int(nsc_val) if pd.notna(nsc_val) else None
                rows.append((
                    str(r[col_map["state_name"]]).strip(),
                    int(r[col_map["sa4_code"]]),
                    str(r[col_map["sa4_name"]]).strip(),
                    int(r[col_map["anzsco4_code"]]),
                    str(r[col_map["anzsco4_name"]]).strip(),
                    date_str, year, month, nsc_emp,
                ))
            except Exception:
                skipped += 1
                continue

        conn.executemany("""
            INSERT INTO nero_sa4
            (state_name, sa4_code, sa4_name, anzsco4_code, anzsco4_name,
             date, year, month, nsc_emp)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, rows)
        conn.commit()
        total += len(rows)

    elapsed = time.time() - start
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT sa4_name) FROM nero_sa4 WHERE state_name = %s", (state,)
    )
    sa4s = cur.fetchone()[0]
    print(f"  State: {state} | Rows: {total:,} | SA4: {sa4s} | Skipped: {skipped} | {elapsed:.1f}s")
    return total


def run_ingestor(filepath=None, folder=None, reset=False):
    db_path = settings.DATABASE_URL
    conn = get_mysql_wrapper(settings)

    print(f"\n{'='*57}")
    print(f"  NERO SA4 Ingestor — per State")
    print(f"  Database: MySQL")
    print(f"{'='*57}")

    cur = conn.cursor()
    if reset:
        cur.execute("DROP TABLE IF EXISTS nero_sa4")
        conn.commit()
        print("\n  Tabel nero_sa4 di-reset")

    cur.execute(CREATE_TABLE)
    conn.commit()
    print("  Tabel nero_sa4 siap\n")

    if folder:
        files = sorted(
            glob.glob(os.path.join(folder, "*.csv")) +
            glob.glob(os.path.join(folder, "*.xlsx")) +
            glob.glob(os.path.join(folder, "*.xls"))
        )
        if not files:
            print(f"  ERROR: Tidak ada file di folder: {folder}")
            sys.exit(1)
        print(f"  Ditemukan {len(files)} file:")
        for f in files:
            print(f"    - {os.path.basename(f)}")
    else:
        if not os.path.exists(filepath):
            print(f"  ERROR: File tidak ditemukan: {filepath}")
            sys.exit(1)
        files = [filepath]

    grand_total = 0
    start_all = time.time()
    for i, f in enumerate(files):
        grand_total += ingest_file(f, conn, file_num=i+1, total_files=len(files))

    print(f"\n  Building indexes...")
    for idx in INDEXES:
        cur.execute(idx)
    conn.commit()
    print(f"  Indexes built")

    elapsed = time.time() - start_all
    cur.execute("SELECT COUNT(*) FROM nero_sa4")
    count = cur.fetchone()[0]

    print(f"\n{'='*57}")
    print(f"  SELESAI! Total: {count:,} rows | {elapsed:.1f}s")

    print(f"\n  Rows per state:")
    cur.execute("SELECT state_name, COUNT(*) as num_rows, COUNT(DISTINCT sa4_code) as sa4s FROM nero_sa4 GROUP BY state_name ORDER BY state_name")
    for r in cur.fetchall():
        print(f"    {r[0]:<5} | {r[1]:>10,} rows | {r[2]:>3} SA4 regions")

    cur.execute("SELECT MIN(date), MAX(date) FROM nero_sa4")
    dr = cur.fetchone()
    print(f"\n  Date range : {dr[0]} → {dr[1]}")
    
    cur.execute('SELECT COUNT(DISTINCT sa4_code) FROM nero_sa4')
    sa4_count = cur.fetchone()[0]
    print(f"  SA4 total  : {sa4_count}")
    
    cur.execute('SELECT COUNT(DISTINCT anzsco4_code) FROM nero_sa4')
    anzsco_count = cur.fetchone()[0]
    print(f"  ANZSCO4    : {anzsco_count}")
    print(f"{'='*57}\n")
    conn.close()


if __name__ == "__main__":
    default_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw/nero_sa4"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder",
        default=default_folder,
        help=f"Folder berisi semua file NERO SA4 (default: {default_folder})",
    )
    parser.add_argument("--file", help="Path ke satu file CSV atau XLSX")
    parser.add_argument("--reset", action="store_true", help="Reset tabel dulu")
    args = parser.parse_args()
    
    if args.file:
        run_ingestor(filepath=args.file, reset=args.reset)
    else:
        run_ingestor(folder=args.folder, reset=args.reset)