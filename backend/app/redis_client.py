import json
from typing import Any, Optional
import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()

_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis():
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


class RedisKeys:
    ACTIVE_INCIDENT = "active_incident:{id}"
    TARGET_METADATA = "target_metadata:{id}"
    STREAM_BUFFER = "stream_buffer:{id}"
    SSE_CHANNEL = "sse_events"

    @staticmethod
    def active_incident(incident_id: str) -> str:
        return f"active_incident:{incident_id}"

    @staticmethod
    def target_metadata(target_id: str) -> str:
        return f"target_metadata:{target_id}"

    @staticmethod
    def stream_buffer(incident_id: str) -> str:
        return f"stream_buffer:{incident_id}"


async def set_active_incident(
    redis: aioredis.Redis,
    incident_id: str,
    data: dict,
    ttl_seconds: int = 86400,
):
    key = RedisKeys.active_incident(incident_id)
    await redis.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()})
    await redis.expire(key, ttl_seconds)


async def get_active_incident(redis: aioredis.Redis, incident_id: str) -> Optional[dict]:
    key = RedisKeys.active_incident(incident_id)
    data = await redis.hgetall(key)
    if not data:
        return None
    result = {}
    for k, v in data.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            result[k] = v
    return result


async def delete_active_incident(redis: aioredis.Redis, incident_id: str):
    await redis.delete(RedisKeys.active_incident(incident_id))


async def push_log_to_buffer(redis: aioredis.Redis, incident_id: str, log_line: str):
    key = RedisKeys.stream_buffer(incident_id)
    await redis.rpush(key, log_line)
    await redis.ltrim(key, -50, -1)  # Keep last 50 lines
    await redis.expire(key, 86400)


async def get_log_buffer(redis: aioredis.Redis, incident_id: str) -> list[str]:
    key = RedisKeys.stream_buffer(incident_id)
    return await redis.lrange(key, 0, -1)


async def publish_sse_event(redis: aioredis.Redis, event_type: str, payload: dict):
    message = json.dumps({"event": event_type, "data": payload})
    await redis.publish(RedisKeys.SSE_CHANNEL, message)


async def get_active_incidents_by_target(redis: aioredis.Redis, target_id: str) -> list[dict]:
    pattern = "active_incident:*"
    incidents = []
    async for key in redis.scan_iter(match=pattern):
        data = await redis.hgetall(key)
        if data and data.get("target_id") == target_id:
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            incidents.append(result)
    return incidents


async def get_all_active_incidents(redis: aioredis.Redis) -> list[dict]:
    pattern = "active_incident:*"
    incidents = []
    async for key in redis.scan_iter(match=pattern):
        data = await redis.hgetall(key)
        if data:
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            result["_key"] = key
            incidents.append(result)
    return incidents
