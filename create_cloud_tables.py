import asyncio
import sys
import os

# Ensures the script can find your 'app' folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.base import Base, engine
# We must import these so SQLAlchemy knows to create them!
from app.models.target import Target
from app.models.check_log import CheckLog

async def build_database():
    print(f"📡 Connecting to AWS RDS...")
    try:
        async with engine.begin() as conn:
            print("🏗️  Building tables: 'targets' and 'check_logs'...")
            # This syncs your Python models to the AWS Cloud
            await conn.run_sync(Base.metadata.create_all)
        print("✅ SUCCESS: Tables are now live in your AWS RDS!")
    except Exception as e:
        print(f"❌ ERROR: Could not create tables. Details: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(build_database())