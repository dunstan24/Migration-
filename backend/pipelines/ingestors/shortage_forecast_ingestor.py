import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper
import pandas as pd
from pathlib import Path

def run_ingestor(folder: str, reset: bool = False):
    folder_path = Path(folder)
    CSV_PATH = folder_path / "Occupation_Shortage_Forecaster_2026_2030_Wide.csv"
    
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    for _candidate in [BASE_DIR, BASE_DIR.parent, BASE_DIR.parent.parent]:
        if (_candidate / "data" / "processed" / "warehouse.db").exists():
            BASE_DIR = _candidate
            break
            
    DB_PATH  = BASE_DIR / "data" / "processed" / "warehouse.db"
    
    print("=" * 60)
    print("INTERLACE — Shortage Forecast Ingestor")
    print("=" * 60)
    
    if not CSV_PATH.exists():
        print(f"\n[ERROR]  CSV not found: {CSV_PATH}")
        sys.exit(1)
        
    print(f"\n[1/3] Loading {CSV_PATH.name} ...")
    df = pd.read_csv(CSV_PATH)
    print(f"  Rows raw: {len(df):,}  |  Cols: {df.columns.tolist()}")

    df["Code"]  = df["Code"].astype(str).str.strip().str.zfill(6)
    df["State"] = df["State"].str.strip().str.upper()

    df = df.rename(columns={
        "Code":       "anzsco_code",
        "Occupation": "occupation",
        "State":      "state",
        "Prob_2026":  "prob_2026",
        "Prob_2027":  "prob_2027",
        "Prob_2028":  "prob_2028",
        "Prob_2029":  "prob_2029",
        "Prob_2030":  "prob_2030",
    })[["anzsco_code", "occupation", "state",
        "prob_2026", "prob_2027", "prob_2028", "prob_2029", "prob_2030"]]

    print(f"  States: {sorted(df['state'].unique().tolist())}")
    print(f"  Unique ANZSCO codes: {df['anzsco_code'].nunique():,}")

    print(f"\n[2/3] Writing to MySQL...")
    conn = get_mysql_wrapper(settings)

    if reset:
        conn.execute("DROP TABLE IF EXISTS shortage_forecast")
        
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shortage_forecast (
            anzsco_code VARCHAR(6) NOT NULL,
            occupation  TEXT NOT NULL,
            state       VARCHAR(5) NOT NULL,
            prob_2026   FLOAT,
            prob_2027   FLOAT,
            prob_2028   FLOAT,
            prob_2029   FLOAT,
            prob_2030   FLOAT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (anzsco_code, state),
            INDEX idx_sf_code (anzsco_code),
            INDEX idx_sf_state (state),
            INDEX idx_sf_2026 (state, prob_2026 DESC)
        )
    """)

    rows = df.to_dict(orient="records")
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        conn.executemany("""
            INSERT INTO shortage_forecast
              (anzsco_code, occupation, state,
               prob_2026, prob_2027, prob_2028, prob_2029, prob_2030)
            VALUES
              (%(anzsco_code)s, %(occupation)s, %(state)s,
               %(prob_2026)s, %(prob_2027)s, %(prob_2028)s, %(prob_2029)s, %(prob_2030)s)
            ON DUPLICATE KEY UPDATE
              occupation = VALUES(occupation),
              prob_2026 = VALUES(prob_2026),
              prob_2027 = VALUES(prob_2027),
              prob_2028 = VALUES(prob_2028),
              prob_2029 = VALUES(prob_2029),
              prob_2030 = VALUES(prob_2030),
              ingested_at = CURRENT_TIMESTAMP
        """, rows[i:i+BATCH])
        print(f"  {min(i+BATCH, len(rows)):,}/{len(rows):,}", end="\r")

    conn.commit()

    result = conn.execute("SELECT COUNT(*) FROM shortage_forecast")
    count = result.fetchone()[0]
    
    result2 = conn.execute(
        "SELECT anzsco_code, occupation, state, prob_2026 FROM shortage_forecast LIMIT 3"
    )
    sample = result2.fetchall()
    conn.close()

    print(f"\n[3/3] Verification")
    print(f"  [OK]  shortage_forecast rows: {count:,}")
    for s in sample:
        print(f"      {s[0]} | {s[1][:30]:30s} | {s[2]} | {s[3]:.3f}")
    print("\n[DONE]  Done! Restart uvicorn — endpoint /api/data/shortage-forecast is live.")


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    folder = BASE_DIR / "data" / "raw" / "shortage_forecast"
    run_ingestor(str(folder), reset=True)