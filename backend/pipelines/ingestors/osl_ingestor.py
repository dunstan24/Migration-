"""
pipelines/ingestors/osl_ingestor.py

Cara pakai:
    python pipelines\\ingestors\\osl_ingestor.py --folder data\\raw\\osl\\ --reset
"""
import argparse, pandas as pd, os, sys, glob, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper

SKILL_LEVEL_DESC = {
    1: "Bachelor Degree or higher",
    2: "Diploma or Associate Degree",
    3: "Certificate III or IV",
    4: "Certificate I or II",
    5: "Certificate I or secondary education",
}

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS osl_shortage (
        id              INTEGER PRIMARY KEY AUTO_INCREMENT,
        year            INTEGER NOT NULL,
        anzsco_code     VARCHAR(6) NOT NULL,
        occupation_name TEXT NOT NULL,
        skill_level     INTEGER,
        skill_level_desc VARCHAR(100),
        national        INTEGER,
        nsw             INTEGER,
        vic             INTEGER,
        qld             INTEGER,
        sa              INTEGER,
        wa              INTEGER,
        tas             INTEGER,
        nt              INTEGER,
        act             INTEGER,
        shortage_state_count INTEGER,
        ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_osl_year       ON osl_shortage(year)",
    "CREATE INDEX IF NOT EXISTS idx_osl_anzsco      ON osl_shortage(anzsco_code)",
    "CREATE INDEX IF NOT EXISTS idx_osl_national    ON osl_shortage(national)",
    "CREATE INDEX IF NOT EXISTS idx_osl_year_anzsco ON osl_shortage(year, anzsco_code)",
]

def extract_year(filename):
    match = re.search(r'(20\d{2})', filename)
    return int(match.group(1)) if match else None

def run_ingestor(folder, reset=False):
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    if not files:
        print(f"Tidak ada file .csv di: {folder}")
        sys.exit(1)

    conn = get_mysql_wrapper(settings)
    cur = conn.cursor()

    print(f"\n{'='*55}")
    print(f"  OSL Ingestor - {len(files)} files")
    print(f"  Database: MySQL")
    print(f"{'='*55}\n")

    if reset:
        cur.execute("DROP TABLE IF EXISTS osl_shortage")
        conn.commit()
        print("Tabel osl_shortage di-reset\n")

    cur.execute(CREATE_TABLE)
    for idx in INDEXES:
        cur.execute(idx)
    conn.commit()
    print("Tabel osl_shortage siap\n")

    total = 0
    for filepath in files:
        fname = os.path.basename(filepath)
        year = extract_year(fname)
        if not year:
            print(f"Skip {fname} - tidak bisa baca tahun")
            continue

        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            print(f"Error {fname} - {e}")
            continue

        rows = []
        for _, r in df.iterrows():
            states = ["NSW","VIC","QLD","SA","WA","TAS","NT","ACT"]
            state_vals = [int(r.get(s, 0) or 0) for s in states]
            shortage_count = sum(state_vals)
            rows.append((
                year, str(r["Code"]), str(r["Occupation"]),
                int(r.get("Skill Level", 0) or 0),
                SKILL_LEVEL_DESC.get(int(r.get("Skill Level", 0) or 0), ""),
                int(r.get("National", 0) or 0),
                int(r.get("NSW", 0) or 0), int(r.get("VIC", 0) or 0),
                int(r.get("QLD", 0) or 0), int(r.get("SA",  0) or 0),
                int(r.get("WA",  0) or 0), int(r.get("TAS", 0) or 0),
                int(r.get("NT",  0) or 0), int(r.get("ACT", 0) or 0),
                shortage_count,
            ))

        cur.executemany("""
            INSERT INTO osl_shortage
            (year, anzsco_code, occupation_name, skill_level, skill_level_desc,
             national, nsw, vic, qld, sa, wa, tas, nt, act, shortage_state_count)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, rows)
        conn.commit()

        national_count = sum(1 for r in rows if r[5] == 1)
        print(f"  {year} | {fname[:40]:<40} OK  {len(rows):>4} occupations, {national_count} national shortage")
        total += len(rows)

    print(f"\n{'='*55}")
    print(f"  Selesai! Total: {total:,} rows")

    print(f"\nSummary per tahun:")
    cur.execute("""
        SELECT year, COUNT(*) as total, SUM(national) as shortage
        FROM osl_shortage GROUP BY year ORDER BY year
    """)
    rows_by_year = cur.fetchall()
    for r in rows_by_year:
        print(f"   {r[0]}: {r[1]} occupations, {r[2]} national shortage")

    print(f"{'='*55}\n")
    conn.close()

if __name__ == "__main__":
    default_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw/osl"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder",
        default=default_folder,
        help=f"Folder berisi file OSL (default: {default_folder})"
    )
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    run_ingestor(folder=args.folder, reset=args.reset)