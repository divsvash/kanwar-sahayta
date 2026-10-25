from redis.asyncio import Redis, ConnectionPool
from app.config import settings

pool = ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
    max_connections=20
)

async def get_redis() -> Redis:
    return Redis(connection_pool=pool)