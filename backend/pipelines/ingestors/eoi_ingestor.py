"""
pipelines/ingestors/eoi_ingestor.py

Membaca file EOI SkillSelect CSV → warehouse.db tabel eoi_records

Struktur kolom CSV:
    As At Month     → MM/YYYY  (contoh: 03/2024)
    Visa Type       → "190SAS Skilled Australian Sponsored" | "491SNR ..."
    Occupation      → "261313 Software Engineer" (ANZSCO + nama)
    EOI Status      → SUBMITTED | INVITED | HOLD | CLOSED | LODGED
    Points          → 35, 40, 45 ... 110
    Count EOIs      → angka atau "<20" (artinya 1–19, disimpan sebagai -1)
    Nominated State → ACT | NSW | VIC | QLD | WA | SA | TAS | NT

Cara pakai:
    # Satu file
    python eoi_ingestor.py --file ../../data/raw/eoi/Data_EOI_ACT_03_2024.csv

    # Semua file sekaligus (2024, 2025, 2026)
    python eoi_ingestor.py --folder ../../data/raw/eoi/

    # Reset tabel dulu baru ingest ulang
    python eoi_ingestor.py --folder ../../data/raw/eoi/ --reset
"""

import argparse
import pandas as pd
import os
import sys
import glob
from datetime import datetime


def configure_console_output():
    """Ensure emoji and other Unicode output do not crash Windows terminals."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


configure_console_output()

# ── Tambah path backend supaya bisa import config ──────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper


# ── Konstanta ───────────────────────────────────────────────
TABLE_NAME   = "eoi_records"
VALID_STATES = {"ACT", "NSW", "VIC", "QLD", "WA", "SA", "TAS", "NT", "ALL STATES"}
VALID_STATUS = {"SUBMITTED", "INVITED", "HOLD", "CLOSED", "LODGED"}

VISA_TYPE_MAP = {
    "190SAS Skilled Australian Sponsored":     "190",
    "491SNR State or Territory Nominated - Regional": "491",
    "189":                                     "189",
}


# ── Helper functions ────────────────────────────────────────
def parse_count(val) -> int:
    """
    '<20' → -1  (artinya antara 1–19, tidak dipublish exact)
    '45'  → 45
    NaN   → 0
    """
    if pd.isna(val):
        return 0
    val = str(val).strip()
    if val == "<20":
        return -1
    try:
        return int(val)
    except ValueError:
        return 0


def parse_month(val: str):
    """
    '03/2024' → datetime(2024, 3, 1)
    Return None kalau tidak bisa parse.
    """
    try:
        return datetime.strptime(str(val).strip(), "%m/%Y")
    except ValueError:
        return None


def extract_anzsco(occupation: str) -> tuple[str, str]:
    """
    '261313 Software Engineer' → ('261313', 'Software Engineer')
    '131112 Sales and Marketing Manager' → ('131112', 'Sales and Marketing Manager')
    """
    occupation = str(occupation).strip()
    parts = occupation.split(" ", 1)
    if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 6:
        return parts[0], parts[1].strip()
    return "", occupation


def map_visa_type(raw: str) -> str:
    """Normalize visa type string ke kode pendek."""
    raw = str(raw).strip()
    for full, short in VISA_TYPE_MAP.items():
        if full in raw or short in raw:
            return short
    # Fallback: ambil angka pertama
    digits = "".join(filter(str.isdigit, raw))[:3]
    return digits if digits else raw


# ── Core: process satu file CSV ─────────────────────────────
def process_file(filepath: str) -> pd.DataFrame:
    """
    Baca 1 file CSV → return DataFrame yang sudah dibersihkan.
    """
    print(f"  → Membaca: {os.path.basename(filepath)}")

    df = pd.read_csv(filepath, dtype=str, keep_default_na=False)

    # Normalize nama kolom (hapus spasi, lowercase)
    df.columns = [c.strip() for c in df.columns]

    # Validasi kolom wajib ada
    required = ["As At Month", "Visa Type", "Occupation", "EOI Status", "Points", "Count EOIs", "Nominated State"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom tidak ditemukan di {filepath}: {missing}")

    # Hapus baris header duplikat (kadang ada di tengah file)
    df = df[df["As At Month"] != "As At Month"].copy()

    # Parse setiap kolom
    df["as_at_month"]    = df["As At Month"].apply(parse_month)
    df["as_at_year"]     = df["as_at_month"].apply(lambda d: d.year  if d else None)
    df["as_at_month_no"] = df["as_at_month"].apply(lambda d: d.month if d else None)
    df["as_at_str"]      = df["As At Month"].str.strip()

    df["visa_type"]      = df["Visa Type"].apply(map_visa_type)
    df["visa_type_full"] = df["Visa Type"].str.strip()

    anzsco_parsed        = df["Occupation"].apply(extract_anzsco)
    df["anzsco_code"]    = anzsco_parsed.apply(lambda x: x[0])
    df["occupation_name"]= anzsco_parsed.apply(lambda x: x[1])

    df["eoi_status"]     = df["EOI Status"].str.strip().str.upper()
    df["points"]         = pd.to_numeric(df["Points"], errors="coerce").fillna(0).astype(int)
    df["count_eois"]     = df["Count EOIs"].apply(parse_count)
    df["state"]          = df["Nominated State"].str.strip().str.upper()

    # Fix: Visa 189 does not have a nominated state, it's marked as "N/A". Map it to "ALL STATES".
    df.loc[df["state"] == "N/A", "state"] = "ALL STATES"

    # Filter baris tidak valid
    df = df[df["as_at_month"].notna()]
    df = df[df["state"].isin(VALID_STATES)]
    df = df[df["eoi_status"].isin(VALID_STATUS)]
    df = df[df["points"] > 0]

    # Pilih kolom final untuk database
    final = df[[
        "as_at_str",
        "as_at_year",
        "as_at_month_no",
        "visa_type",
        "visa_type_full",
        "anzsco_code",
        "occupation_name",
        "eoi_status",
        "points",
        "count_eois",
        "state",
    ]].copy()

    print(f"     [OK] {len(final):,} baris valid")
    return final


# ── Database: buat tabel ────────────────────────────────────
def create_table(conn, reset: bool = False):
    """Buat tabel eoi_records kalau belum ada."""
    if reset:
        conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        print(f"  🗑  Tabel {TABLE_NAME} di-reset")

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id               INTEGER PRIMARY KEY AUTO_INCREMENT,

            -- Waktu snapshot
            as_at_str        VARCHAR(20) NOT NULL,        -- '03/2024'
            as_at_year       INTEGER NOT NULL,      -- 2024
            as_at_month_no   INTEGER NOT NULL,      -- 3

            -- Visa
            visa_type        VARCHAR(10) NOT NULL,         -- '190' | '491' | '189'
            visa_type_full   VARCHAR(255),                  -- nama lengkap

            -- Occupation
            anzsco_code      VARCHAR(10),                  -- '261313'
            occupation_name  TEXT NOT NULL,         -- 'Software Engineer'

            -- EOI data
            eoi_status       VARCHAR(20) NOT NULL,         -- SUBMITTED|INVITED|HOLD|CLOSED|LODGED
            points           INTEGER NOT NULL,      -- 35–110
            count_eois       INTEGER NOT NULL,      -- angka, atau -1 kalau '<20'
            state            VARCHAR(20) NOT NULL,         -- ACT|NSW|VIC|QLD|WA|SA|TAS|NT

            -- Metadata
            ingested_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE KEY `unique_eoi_record` (
                `as_at_str`, `visa_type`, `anzsco_code`, 
                `eoi_status`, `points`, `state`, `count_eois`
            ),
            KEY `idx_eoi_state`      (state),
            KEY `idx_eoi_anzsco`     (anzsco_code),
            KEY `idx_eoi_status`     (eoi_status),
            KEY `idx_eoi_year`       (as_at_year),
            KEY `idx_eoi_visa_type`  (visa_type)
        )
    """)

    conn.commit()
    print(f"  [OK] Tabel {TABLE_NAME} siap")


# ── Database: insert data ───────────────────────────────────
def insert_data(conn, df: pd.DataFrame, source_file: str):
    """Insert DataFrame ke tabel eoi_records."""
    before = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]

    # Convert DataFrame to list of tuples for batch insert
    rows = [
        (
            row['as_at_str'],
            row['as_at_year'],
            row['as_at_month_no'],
            row['visa_type'],
            row['visa_type_full'],
            row['anzsco_code'],
            row['occupation_name'],
            row['eoi_status'],
            row['points'],
            row['count_eois'],
            row['state'],
        )
        for _, row in df.iterrows()
    ]

    # Batch insert with larger chunks to reduce commit overhead
    BATCH_SIZE = 5000
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i+BATCH_SIZE]
        conn.executemany(f"""
            INSERT INTO {TABLE_NAME}
            (as_at_str, as_at_year, as_at_month_no, visa_type, visa_type_full,
             anzsco_code, occupation_name, eoi_status, points, count_eois, state)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
             ingested_at = CURRENT_TIMESTAMP
        """, batch)
        print(f"  💾 {min(i+BATCH_SIZE, len(rows)):,}/{len(rows):,}", end="\r")

    after = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    inserted = after - before
    print(f"  💾 {inserted:,} baris dimasukkan dari {os.path.basename(source_file)}         ")
    return inserted


# ── Main function ───────────────────────────────────────────
def run_ingestor(file: str = None, folder: str = None, reset: bool = False):
    """
    Jalankan ingestor.
    file   → path ke satu file CSV
    folder → path ke folder berisi banyak file CSV
    reset  → hapus tabel dulu sebelum ingest
    """
    # Kumpulkan semua file yang akan diproses
    files_to_process = []

    if file:
        if not os.path.exists(file):
            raise FileNotFoundError(f"File tidak ditemukan: {file}")
        files_to_process = [file]

    elif folder:
        if not os.path.exists(folder):
            raise FileNotFoundError(f"Folder tidak ditemukan: {folder}")
        files_to_process = sorted(glob.glob(os.path.join(folder, "*.csv")))
        if not files_to_process:
            raise ValueError(f"Tidak ada file CSV di folder: {folder}")

    else:
        # Default: cari di folder dari settings
        eoi_dir = settings.EOI_DATA_DIR
        files_to_process = sorted(glob.glob(os.path.join(eoi_dir, "*.csv")))
        if not files_to_process:
            raise ValueError(f"Tidak ada file CSV di {eoi_dir} — copy file EOI kamu ke sana dulu")

    print(f"\n{'='*55}")
    print(f"  EOI SkillSelect Ingestor")
    print(f"  {len(files_to_process)} file ditemukan")
    print(f"{'='*55}")

    # Pastikan folder database ada
    db_dir = '.'
    os.makedirs(db_dir, exist_ok=True)

    # Koneksi ke SQLite
    conn = get_mysql_wrapper(settings)
    print(f"\n[DB] Database: {settings.DATABASE_URL}")

    try:
        # Buat / reset tabel
        create_table(conn, reset=reset)

        # Proses setiap file
        total_inserted = 0
        errors = []

        for filepath in files_to_process:
            print(f"\n📄 {os.path.basename(filepath)}")
            try:
                df = process_file(filepath)
                inserted = insert_data(conn, df, filepath)
                total_inserted += inserted
            except Exception as e:
                errors.append((filepath, str(e)))
                print(f"  [ERROR] Error: {e}")

        conn.commit()

        # Summary
        total_in_db = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
        print(f"\n{'='*55}")
        print(f"  [OK] Selesai!")
        print(f"  Total baris dimasukkan : {total_inserted:,}")
        print(f"  Total baris di database: {total_in_db:,}")
        if errors:
            print(f"  ⚠️  {len(errors)} file gagal:")
            for f, e in errors:
                print(f"     {os.path.basename(f)}: {e}")
        print(f"{'='*55}\n")

        # Quick stats
        print("[STATS] Quick stats:")
        for row in conn.execute(f"""
            SELECT as_at_year, visa_type, eoi_status, COUNT(*) as num_rows
            FROM {TABLE_NAME}
            GROUP BY as_at_year, visa_type, eoi_status
            ORDER BY as_at_year, visa_type, eoi_status
        """):
            print(f"  {row[0]} | {row[1]:5} | {row[2]:10} | {row[3]:,} rows")

    finally:
        conn.close()


# ── CLI entry point ─────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EOI SkillSelect CSV Ingestor")
    parser.add_argument("--file",   help="Path ke satu file CSV")
    parser.add_argument("--folder", help="Path ke folder berisi banyak CSV")
    parser.add_argument("--reset",  action="store_true", help="Reset tabel sebelum ingest")
    args = parser.parse_args()

    run_ingestor(file=args.file, folder=args.folder, reset=args.reset)
