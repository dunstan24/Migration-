"""
Initialize authentication schema in database.
Run this once to create users and user_activity_logs tables with proper indexes.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from db.mysql_wrapper import get_mysql_wrapper, SqliteToMysqlWrapper
from db.database import sync_engine

from pathlib import Path
from config import settings


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

# Read schema
backend_path = Path(__file__).parent
schema_file = backend_path / "db" / "schema_auth.sql"

if not schema_file.exists():
    print(f"❌ Schema file not found: {schema_file}")
    sys.exit(1)

# Connect to database
print(f"📂 Connecting to MySQL...")

try:
    conn = get_mysql_wrapper(settings)
    cursor = conn.cursor()
    
    # Read and execute schema
    print("🔨 Creating tables and indexes...")
    # Read schema and execute statements one by one
    with open(schema_file, 'r') as f:
        schema_sql = f.read()
    
    # Simple split by ';' (assuming no complex semicolons in strings)
    statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
    for statement in statements:
        # Convert AUTOINCREMENT if any
        statement = statement.replace('AUTOINCREMENT', 'AUTO_INCREMENT')
        statement = statement.replace('INSERT OR IGNORE', 'INSERT IGNORE')
        
        # MySQL doesn't support CREATE INDEX IF NOT EXISTS natively in all versions
        if statement.startswith('CREATE INDEX IF NOT EXISTS'):
            statement = statement.replace('CREATE INDEX IF NOT EXISTS', 'CREATE INDEX')
            try:
                cursor.execute(statement)
            except Exception as e:
                # If it already exists, error 1061 is thrown. We can ignore it.
                if "1061" not in str(e) and "Duplicate" not in str(e):
                    print(f"Warning: {e}")
        else:
            try:
                cursor.execute(statement)
            except Exception as e:
                print(f"Statement failed: {statement}\nError: {e}")
    
    conn.commit()
    
    print("✅ Schema created successfully!")
    
    # Verify
    user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print(f"   Users: {user_count}")
    
    activity_count = cursor.execute("SELECT COUNT(*) FROM user_activity_logs").fetchone()[0]
    print(f"   Activity logs: {activity_count}")
    
    # Check indexes
    print("\n📊 Indexes created:")
    for row in cursor.execute("SHOW INDEXES FROM users").fetchall():
        if row[2] != 'PRIMARY':
            print(f"   ✓ {row[2]} (users)")
    
    for row in cursor.execute("SHOW INDEXES FROM user_activity_logs").fetchall():
        if row[2] != 'PRIMARY':
            print(f"   ✓ {row[2]} (user_activity_logs)")
    
    conn.close()

except Exception as e:
    print(f"❌ Error: {str(e)}")
    sys.exit(1)
