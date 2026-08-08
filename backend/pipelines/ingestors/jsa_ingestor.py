r"""
pipelines/ingestors/jsa_ingestor.py

Membaca semua file JSA Occupation xlsx → warehouse.db
Setiap file = 1 occupation, berisi banyak sheet.

Tabel yang dibuat:
    jsa_monthly_ads        → Monthly Time series (job ads)
    jsa_quarterly_employment → Quarterly Time series (employment + vacancy)
    jsa_demographics       → Demographic data (age, gender)
    jsa_education          → Main fields of education
    jsa_shortage           → Shortage ratings
    jsa_projected          → Projected employment
    jsa_recruitment        → Employer recruitment insights
    jsa_top10              → Top 10s (SA4 regions)
    jsa_mobility           → Occupational Mobility

Cara pakai:
    python pipelines\ingestors\jsa_ingestor.py --folder ..\data\raw\jsa\ --reset
    python pipelines\ingestors\jsa_ingestor.py --folder ..\data\raw\jsa\
"""
import argparse
import pandas as pd
import os
import sys
import glob
import traceback


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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine


# ── Table definitions ─────────────────────────────────────────
TABLES = {
    "jsa_monthly_ads": """
        CREATE TABLE IF NOT EXISTS jsa_monthly_ads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_name     VARCHAR(255) NOT NULL,
            anzsco_level    INTEGER,
            occ_group       VARCHAR(100),
            job_ads_date    VARCHAR(20),
            job_ads_count   INTEGER,
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
    "jsa_quarterly_employment": """
        CREATE TABLE IF NOT EXISTS jsa_quarterly_employment (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_name     VARCHAR(255) NOT NULL,
            anzsco_level    INTEGER,
            occ_group       VARCHAR(100),
            quarter         VARCHAR(20),
            employment      INTEGER,
            vacancy_rate    REAL,
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
    "jsa_demographics": """
        CREATE TABLE IF NOT EXISTS jsa_demographics (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_name     VARCHAR(255) NOT NULL,
            anzsco_level    INTEGER,
            category        VARCHAR(100),
            segment         VARCHAR(255),
            share           REAL,
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
    "jsa_education": """
        CREATE TABLE IF NOT EXISTS jsa_education (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_name     VARCHAR(255) NOT NULL,
            anzsco_level    INTEGER,
            field           VARCHAR(255),
            edu_level       VARCHAR(100),
            share           REAL,
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
    "jsa_shortage": """
        CREATE TABLE IF NOT EXISTS jsa_shortage (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_name     VARCHAR(255) NOT NULL,
            anzsco_level    INTEGER,
            shortage_rating VARCHAR(100),
            shortage_driver VARCHAR(255),
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
    "jsa_projected": """
        CREATE TABLE IF NOT EXISTS jsa_projected (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_name     VARCHAR(255) NOT NULL,
            anzsco_level    INTEGER,
            projected_year  INTEGER,
            projected_change VARCHAR(100),
            occ_group       VARCHAR(100),
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
    "jsa_recruitment": """
        CREATE TABLE IF NOT EXISTS jsa_recruitment (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_name     VARCHAR(255) NOT NULL,
            anzsco_level    INTEGER,
            filled_vacancies REAL,
            avg_applicants  REAL,
            avg_qualified   REAL,
            avg_suitable    REAL,
            avg_experience  REAL,
            pct_require_exp REAL,
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
    "jsa_top10": """
        CREATE TABLE IF NOT EXISTS jsa_top10 (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_name     VARCHAR(255) NOT NULL,
            anzsco_level    INTEGER,
            rank_category   VARCHAR(100),
            rank_position   INTEGER,
            sa4_code        VARCHAR(20),
            sa4_name        VARCHAR(255),
            value           REAL,
            category_date   VARCHAR(20),
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
    "jsa_mobility": """
        CREATE TABLE IF NOT EXISTS jsa_mobility (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            anzsco_code     VARCHAR(10) NOT NULL,
            anzsco_level    INTEGER,
            mobility_type   VARCHAR(100),
            year_origin     INTEGER,
            code_origin     VARCHAR(20),
            name_origin     VARCHAR(255),
            year_dest       INTEGER,
            code_dest       VARCHAR(20),
            name_dest       VARCHAR(255),
            people_movement INTEGER,
            ingested_at     TEXT DEFAULT (datetime('now'))
        )
    """,
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_jsa_monthly_code    ON jsa_monthly_ads(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_jsa_quarterly_code  ON jsa_quarterly_employment(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_jsa_demo_code       ON jsa_demographics(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_jsa_edu_code        ON jsa_education(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_jsa_shortage_code   ON jsa_shortage(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_jsa_projected_code  ON jsa_projected(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_jsa_recruit_code    ON jsa_recruitment(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_jsa_top10_code      ON jsa_top10(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_jsa_mobility_code   ON jsa_mobility(anzsco_code)",
]


def safe(val):
    """Convert NaN/None to None for MySQL."""
    if pd.isna(val) if not isinstance(val, (list, dict)) else False:
        return None
    return val


def read_sheet(xl, sheet_name):
    """Read sheet safely — return empty df if sheet not found."""
    if sheet_name not in xl.sheet_names:
        return pd.DataFrame()
    try:
        return xl.parse(sheet_name)
    except Exception:
        return pd.DataFrame()


def process_file(filepath, conn):
    """Process one JSA xlsx file → insert all sheets to DB."""
    try:
        xl = pd.ExcelFile(filepath)
    except Exception as e:
        return 0, f"Cannot open: {e}"

    inserted = 0

    # ── Monthly Time series ───────────────────────────────────
    df = read_sheet(xl, "Monthly Time series")
    if not df.empty and "anzsco_code" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code", "")) or ""),
                str(safe(r.get("anzsco_name", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("occupation_group(anzsco1)")),
                str(safe(r.get("jobAds_date", "")) or ""),
                safe(r.get("jobAds_anzsco4")),
            ))
        conn.executemany("""
            INSERT INTO jsa_monthly_ads
            (anzsco_code, anzsco_name, anzsco_level, occ_group, job_ads_date, job_ads_count)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    # ── Quarterly Time series ─────────────────────────────────
    df = read_sheet(xl, "Quarterly Time series")
    if not df.empty and "anzsco_code" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code", "")) or ""),
                str(safe(r.get("anzsco_name", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("occupation_group(anzsco1)")),
                str(safe(r.get("quarter", "")) or ""),
                safe(r.get("employment_anzsco4")),
                safe(r.get("vacancy_rate_anzsco4")),
            ))
        conn.executemany("""
            INSERT INTO jsa_quarterly_employment
            (anzsco_code, anzsco_name, anzsco_level, occ_group, quarter, employment, vacancy_rate)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    # ── Demographic data ──────────────────────────────────────
    df = read_sheet(xl, "Demographic data")
    if not df.empty and "anzsco_code" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code", "")) or ""),
                str(safe(r.get("anzsco_name", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("category")),
                safe(r.get("category_segment")),
                safe(r.get("category_segment_share_anzsco4")),
            ))
        conn.executemany("""
            INSERT INTO jsa_demographics
            (anzsco_code, anzsco_name, anzsco_level, category, segment, share)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    # ── Main fields of education ──────────────────────────────
    df = read_sheet(xl, "Main fields of education")
    if not df.empty and "anzsco_code" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code", "")) or ""),
                str(safe(r.get("anzsco_name", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("top5_fields_of_education")),
                safe(r.get("level_of_education")),
                safe(r.get("level_of_education_share")),
            ))
        conn.executemany("""
            INSERT INTO jsa_education
            (anzsco_code, anzsco_name, anzsco_level, field, edu_level, share)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    # ── Shortage ratings ──────────────────────────────────────
    df = read_sheet(xl, "Shortage ratings")
    if not df.empty and "anzsco_code" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code", "")) or ""),
                str(safe(r.get("anzsco_name", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("shortage_rating")),
                safe(r.get("shortage_driver")),
            ))
        conn.executemany("""
            INSERT INTO jsa_shortage
            (anzsco_code, anzsco_name, anzsco_level, shortage_rating, shortage_driver)
            VALUES (%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    # ── Projected employment ──────────────────────────────────
    df = read_sheet(xl, "Projected employment")
    if not df.empty and "anzsco_code" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code", "")) or ""),
                str(safe(r.get("anzsco_name", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("projected_year")),
                safe(r.get("projected_change_anzsco4")),
                safe(r.get("occupation_group(anzsco1)")),
            ))
        conn.executemany("""
            INSERT INTO jsa_projected
            (anzsco_code, anzsco_name, anzsco_level, projected_year, projected_change, occ_group)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    # ── Employer recruitment insights ─────────────────────────
    df = read_sheet(xl, "Employer recruitment insights")
    if not df.empty and "anzsco_code" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code", "")) or ""),
                str(safe(r.get("anzsco_name", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("filled_vacancies")),
                safe(r.get("average_applicants_per_vacancy")),
                safe(r.get("average_qualified_applicants_per_vacancy")),
                safe(r.get("average_suitable_applicants_per_vacancy")),
                safe(r.get("average_years_of_experience")),
                safe(r.get("employers_requiring_experience")),
            ))
        conn.executemany("""
            INSERT INTO jsa_recruitment
            (anzsco_code, anzsco_name, anzsco_level, filled_vacancies,
             avg_applicants, avg_qualified, avg_suitable, avg_experience, pct_require_exp)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    # ── Top 10s ───────────────────────────────────────────────
    df = read_sheet(xl, "Top 10s")
    if not df.empty and "anzsco_code" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code", "")) or ""),
                str(safe(r.get("anzsco_name", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("rank_category")),
                safe(r.get("rank_position")),
                safe(r.get("top_sa4_region_code")),
                safe(r.get("top_sa4_region_name")),
                safe(r.get("category_value")),
                str(safe(r.get("category_date", "")) or ""),
            ))
        conn.executemany("""
            INSERT INTO jsa_top10
            (anzsco_code, anzsco_name, anzsco_level, rank_category, rank_position,
             sa4_code, sa4_name, value, category_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    # ── Occupational Mobility ─────────────────────────────────
    df = read_sheet(xl, "Occupational Mobility")
    if not df.empty and "anzsco_level" in df.columns:
        rows = []
        for _, r in df.iterrows():
            rows.append((
                str(safe(r.get("anzsco_code_destination", "")) or ""),
                safe(r.get("anzsco_level")),
                safe(r.get("Occupational mobility")),
                safe(r.get("year_origin")),
                str(safe(r.get("anzsco_code_origin", "")) or ""),
                safe(r.get("anzsco_name_origin")),
                safe(r.get("year_destination")),
                str(safe(r.get("anzsco_code_destination", "")) or ""),
                safe(r.get("anzsco_name_destination")),
                safe(r.get("people_movement")),
            ))
        conn.executemany("""
            INSERT INTO jsa_mobility
            (anzsco_code, anzsco_level, mobility_type, year_origin,
             code_origin, name_origin, year_dest, code_dest, name_dest, people_movement)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, rows)
        inserted += len(rows)

    return inserted, None


def run_ingestor(folder, reset=False):
    files = sorted(glob.glob(os.path.join(folder, "*.xlsx")))
    if not files:
        print(f"❌ Tidak ada file .xlsx di: {folder}")
        sys.exit(1)

    db_path = settings.DATABASE_URL
    print(f"[DB] Database: {db_path}")
    conn = get_mysql_wrapper(settings)

    print(f"\n{'='*60}")
    print(f"  JSA Ingestor — {len(files)} files")
    print(f"  Database: {db_path}")
    print(f"{'='*60}\n")

    # Create/reset tables
    if reset:
        for table in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        print("🗑  Semua tabel JSA di-reset\n")

    for sql in TABLES.values():
        conn.execute(sql)
    for idx in INDEXES:
        conn.execute(idx)
    conn.commit()
    print(f"✅ {len(TABLES)} tabel JSA siap\n")

    # Process files
    total_inserted = 0
    errors = []

    for i, filepath in enumerate(files, 1):
        fname = os.path.basename(filepath)
        print(f"[{i:>4}/{len(files)}] {fname[:55]:<55}", end=" ", flush=True)
        try:
            inserted, err = process_file(filepath, conn)
            if err:
                print(f"❌ {err}")
                errors.append((fname, err))
            else:
                print(f"✅ {inserted:>6,} rows")
                total_inserted += inserted
            # Commit every 10 files
            if i % 10 == 0:
                conn.commit()
        except Exception as e:
            print(f"❌ {e}")
            errors.append((fname, str(e)))

    conn.commit()

    # Summary
    print(f"\n{'='*60}")
    print(f"  ✅ Selesai!")
    print(f"  Files processed : {len(files) - len(errors):,}")
    print(f"  Total rows      : {total_inserted:,}")
    print(f"  Errors          : {len(errors)}")

    if errors:
        print(f"\n  ❌ Files yang gagal:")
        for fname, err in errors[:10]:
            print(f"     {fname}: {err}")

    # Quick stats per table
    print(f"\n📊 Rows per tabel:")
    for table in TABLES:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"   {table:<35} {count:>10,}")
        except:
            pass

    print(f"{'='*60}\n")
    conn.close()


if __name__ == "__main__":
    default_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw/jsa"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder",
        default=default_folder,
        help=f"Folder berisi file JSA xlsx (default: {default_folder})",
    )
    parser.add_argument("--reset",  action="store_true", help="Reset tabel dulu")
    args = parser.parse_args()
    run_ingestor(folder=args.folder, reset=args.reset)