import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from persistence.database import init_db, check_db_connection


async def main():
    print("Initializing database...")
    ok = await check_db_connection()
    if not ok:
        print("WARNING: Could not connect to database. Tables will be created when connection is available.")
        return
    await init_db()
    print("Database initialized successfully.")


if __name__ == "__main__":
    asyncio.run(main())
