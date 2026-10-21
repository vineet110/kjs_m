import asyncio

async def worker_loop():
    print("PostgreSQL SKIP LOCKED background worker started.")
    while True:
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(worker_loop())
