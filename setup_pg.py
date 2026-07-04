import asyncio
import asyncpg

async def setup_db():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/postgres')
    try:
        # Create user cronwave with password cronwave if it doesn't exist
        await conn.execute("CREATE ROLE cronwave WITH LOGIN PASSWORD 'cronwave'")
        print("Created role cronwave")
    except asyncpg.exceptions.DuplicateObjectError:
        print("Role cronwave already exists")
    
    try:
        # Create database cronwave owned by cronwave
        await conn.execute("CREATE DATABASE cronwave OWNER cronwave")
        print("Created database cronwave")
    except asyncpg.exceptions.DuplicateDatabaseError:
        print("Database cronwave already exists")
        
    await conn.close()

asyncio.run(setup_db())
