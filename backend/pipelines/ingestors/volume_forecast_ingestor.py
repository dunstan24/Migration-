import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper

from pathlib import Path
import pandas as pd


def run_ingestor(folder: str, reset: bool = False):
    folder_path = Path(folder)

    names = [
        "final_migration_forecast_2030.csv",
        "migration_forecast_2030.csv",
        "migration_volume_forecast.csv",
    ]
    csv_path = None
    for name in names:
        p = folder_path / name
        if p.exists():
            csv_path = p
            break

    if not csv_path:
        print(f"[ERROR] Forecast CSV not found in {folder}")
        sys.exit(1)

    print("=" * 55)
    print("INTERLACE -- Migration Volume Forecast Ingestor")
    print("=" * 55)
    print(f"CSV : {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"\nRows loaded: {len(df)}")

    df["month"]    = pd.to_datetime(df["ds"], format="mixed", dayfirst=False).dt.strftime("%Y-%m-%d")
    df["year"]     = pd.to_datetime(df["ds"], format="mixed", dayfirst=False).dt.year
    df["month_no"] = pd.to_datetime(df["ds"], format="mixed", dayfirst=False).dt.month

    for col in ["yhat", "yhat_lower_95", "yhat_upper_95", "yhat_lower_80", "yhat_upper_80"]:
        df[col] = df[col].round(2)

    db = get_mysql_wrapper(settings)  # Pass settings parameter

    if reset:
        db.execute("DROP TABLE IF EXISTS migration_volume_forecast")

    db.execute("""
        CREATE TABLE IF NOT EXISTS migration_volume_forecast (
            month           VARCHAR(10)  PRIMARY KEY,
            year            INT,
            month_no        INT,
            yhat            DOUBLE,
            yhat_lower_95   DOUBLE,
            yhat_upper_95   DOUBLE,
            yhat_lower_80   DOUBLE,
            yhat_upper_80   DOUBLE
        )
    """)

    rows = [
        (
            row["month"], int(row["year"]), int(row["month_no"]),
            row["yhat"], row["yhat_lower_95"], row["yhat_upper_95"],
            row["yhat_lower_80"], row["yhat_upper_80"],
        )
        for _, row in df.iterrows()
    ]

    db.executemany("""
        INSERT INTO migration_volume_forecast
            (month, year, month_no, yhat, yhat_lower_95, yhat_upper_95, yhat_lower_80, yhat_upper_80)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            year          = VALUES(year),
            month_no      = VALUES(month_no),
            yhat          = VALUES(yhat),
            yhat_lower_95 = VALUES(yhat_lower_95),
            yhat_upper_95 = VALUES(yhat_upper_95),
            yhat_lower_80 = VALUES(yhat_lower_80),
            yhat_upper_80 = VALUES(yhat_upper_80)
    """, rows)

    db.commit()
    
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM migration_volume_forecast")
    count = cur.fetchone()[0]
    
    cur.execute("SELECT month, yhat FROM migration_volume_forecast ORDER BY month ASC  LIMIT 1")
    first = cur.fetchone()
    
    cur.execute("SELECT month, yhat FROM migration_volume_forecast ORDER BY month DESC LIMIT 1")
    last = cur.fetchone()

    print(f"\n[OK] migration_volume_forecast: {count} rows")
    if count > 0:
        print(f"     Range: {first[0]} ({first[1]:,.0f}) -> {last[0]} ({last[1]:,.0f})")
    print("\nDone! Restart backend to expose the new endpoint.")


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    folder = BASE_DIR / "data" / "raw" / "volume_forecast"
    run_ingestor(str(folder), reset=True)