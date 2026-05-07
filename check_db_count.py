import asyncio
from sqlalchemy import func, select
from app.db.base import AsyncSessionLocal
from app.models.target import Target
from app.models.check_log import CheckLog

async def check_data():
    async with AsyncSessionLocal() as session:
        # Count targets
        target_count = await session.scalar(select(func.count()).select_from(Target))
        # Count logs
        log_count = await session.scalar(select(func.count()).select_from(CheckLog))
        
        print(f"📊 Cloud Status:")
        print(f"Total Targets: {target_count}")
        print(f"Total Logs: {log_count}")

if __name__ == "__main__":
    asyncio.run(check_data())