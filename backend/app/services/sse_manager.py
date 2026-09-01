"""
SSE Manager: Real-time event broadcasting via Redis Pub/Sub.

Architecture:
  Workers/Services → redis.publish(SSE_CHANNEL, event_json)
       ↓
  SSE Router → redis.subscribe(SSE_CHANNEL) → EventSourceResponse → Browser

Multiple browser clients can connect simultaneously. Each subscribes to the same
Redis channel and receives all broadcast events.
"""
import asyncio
import json
import logging
from typing import AsyncIterator

import redis.asyncio as aioredis
from app.config import get_settings
from app.redis_client import RedisKeys, get_redis

logger = logging.getLogger(__name__)
settings = get_settings()


async def event_generator(request) -> AsyncIterator[dict]:
    """
    SSE event generator for FastAPI endpoint.
    Subscribes to Redis pub/sub channel and yields events to the browser.
    Handles client disconnect cleanly.
    """
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(RedisKeys.SSE_CHANNEL)

    # Send a heartbeat first so the browser knows connection is alive
    yield {"event": "connected", "data": json.dumps({"status": "ok"})}

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info("SSE client disconnected.")
                break

            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                try:
                    payload = json.loads(message["data"])
                    event_type = payload.get("event", "update")
                    event_data = payload.get("data", {})
                    yield {
                        "event": event_type,
                        "data": json.dumps(event_data),
                    }
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Malformed SSE message: {e}")

            # Heartbeat every 15 seconds to keep connection alive
            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"SSE generator error: {e}", exc_info=True)
    finally:
        try:
            await pubsub.unsubscribe(RedisKeys.SSE_CHANNEL)
            await pubsub.aclose()
        except Exception:
            pass


async def broadcast(event_type: str, payload: dict):
    """
    Publish an SSE event to all connected clients via Redis.
    """
    redis = await get_redis()
    message = json.dumps({"event": event_type, "data": payload})
    await redis.publish(RedisKeys.SSE_CHANNEL, message)


class SSEEvents:
    """Event type constants matching the API contract spec."""
    INCIDENT_CREATED = "incident_created"
    INCIDENT_UPDATE = "incident_update"
    GEMINI_THOUGHT = "gemini_thought"
    GEMINI_FINAL = "gemini_final"
    LOKI_LOGS = "loki_logs"
    HEARTBEAT = "heartbeat"
