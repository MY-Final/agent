from redis.asyncio import Redis

from app.core.config import settings


class RedisManager:
    def __init__(self) -> None:
        self._client: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("Redis 客户端尚未初始化")
        return self._client

    async def connect(self) -> None:
        self._client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            socket_timeout=settings.redis_connect_timeout_seconds,
        )
        try:
            await self._client.ping()
        except Exception:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def ping(self) -> bool:
        if self._client is None:
            await self.connect()
        return bool(await self.client.ping())


redis_manager = RedisManager()
