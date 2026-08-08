import sys
import asyncio
import logging
from pathlib import Path
import time
sys.path.insert(0, str(Path.cwd()))

# Configure logging to show up in the console
logging.basicConfig(level=logging.INFO, format='%(message)s')

from rag.ingest import ingest_migration_documents

print("Starting ingestion...")
start_time = time.time()

try:
    result = asyncio.run(ingest_migration_documents())
    elapsed = time.time() - start_time
    
    print("\n" + "="*50)
    print("INGESTION SUCCESS!")
    print("="*50)
    print(f"Status: {result.get('status')}")
    print(f"Total documents: {result.get('total_documents')}")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    
    if 'breakdown' in result:
        print("\nBreakdown by phase:")
        for phase, count in result['breakdown'].items():
            print(f"  {phase}: {count} docs")
            
except Exception as e:
    elapsed = time.time() - start_time
    print(f"\nINGESTION FAILED after {elapsed:.1f} seconds")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
