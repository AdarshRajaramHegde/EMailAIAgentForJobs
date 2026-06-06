import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scheduler import run_processing_pipeline
from database.db import init_db

async def main():
    print("Initializing DB...")
    init_db()
    print("Running pipeline...")
    # This will use the mock settings because we haven't loaded .env secrets in this shell environment ideally,
    # but we want to see if it even reaches the scoring/email part and if it has name errors.
    try:
        await run_processing_pipeline()
        print("✅ Pipeline run complete (or skipped if no jobs).")
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
