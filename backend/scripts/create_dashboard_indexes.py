from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine
 # Keep for potential fallback
import time
import sys
import os

# Add parent dir to path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine


def add_indexes():
    print(f"Connecting to {settings.DATABASE_URL}...")
    conn = get_mysql_wrapper(settings)
    c = conn.cursor()
    
    start = time.time()
    
    print("1/5: idx_eoi_year_month (For finding latest snapshot)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_eoi_year_month ON eoi_records(as_at_year DESC, as_at_month_no DESC);")
    
    print("2/5: idx_eoi_status_month (For fast filtering by status and snapshot)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_eoi_status_month ON eoi_records(eoi_status, as_at_str);")
    
    print("3/5: idx_eoi_anzsco (For quick occupation lookups)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_eoi_anzsco ON eoi_records(anzsco_code);")
    
    print("4/5: idx_eoi_grouping (For fast aggregations by state and visa type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_eoi_grouping ON eoi_records(anzsco_code, eoi_status, state, visa_type);")

    print("5/5: idx_osl_year (For filtering shortage by year)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_osl_year ON osl_shortage(year);")
    
    conn.commit()
    conn.close()
    
    print(f"Finished adding all indexes in {time.time() - start:.2f} seconds!")

if __name__ == "__main__":
    add_indexes()
