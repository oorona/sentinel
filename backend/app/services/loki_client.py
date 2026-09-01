"""
Loki HTTP API client.
Handles log queries and tail streaming for incident context.
"""
import time
from typing import Optional, AsyncIterator
import aiohttp
from app.config import get_settings

settings = get_settings()


class LokiClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.LOKI_URL).rstrip("/")

    async def query_logs(
        self,
        loki_label: str,
        limit: int = None,
        start_ns: Optional[int] = None,
        end_ns: Optional[int] = None,
    ) -> list[dict]:
        """
        Query Loki logs for a target using LogQL.

        Args:
            loki_label: LogQL label selector, e.g. 'app="oracle-db",host="db-prod-01"'
            limit: Max number of log lines. Defaults to LOKI_LOG_LINES.
            start_ns: Start time in nanoseconds. Defaults to 1 hour ago.
            end_ns: End time in nanoseconds. Defaults to now.

        Returns:
            List of log entries {timestamp_ns, line, labels}.
        """
        limit = limit or settings.LOKI_LOG_LINES
        now_ns = int(time.time() * 1e9)
        if end_ns is None:
            end_ns = now_ns
        if start_ns is None:
            start_ns = now_ns - int(3600 * 1e9)  # 1 hour ago

        query = f'{{{loki_label}}}'
        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {
            "query": query,
            "limit": limit,
            "start": start_ns,
            "end": end_ns,
            "direction": "backward",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return self._parse_loki_response(data)

    def _parse_loki_response(self, data: dict) -> list[dict]:
        """Parse Loki query_range response into flat log entries."""
        entries = []
        results = data.get("data", {}).get("result", [])
        for stream in results:
            labels = stream.get("stream", {})
            for ts_ns, line in stream.get("values", []):
                entries.append({
                    "timestamp_ns": int(ts_ns),
                    "timestamp_sec": int(ts_ns) / 1e9,
                    "line": line,
                    "labels": labels,
                })
        # Sort by timestamp ascending
        entries.sort(key=lambda x: x["timestamp_ns"])
        return entries

    async def get_logs_snapshot(self, loki_label: str, lines: int = 100) -> str:
        """
        Get a plain-text snapshot of the last N log lines.
        Used for LLM context injection.
        """
        if not loki_label:
            return "No Loki label configured for this target."

        entries = await self.query_logs(loki_label, limit=lines)
        if not entries:
            return "No log data available for this target in the last hour."

        import datetime
        log_lines = []
        for entry in entries[-lines:]:
            ts = datetime.datetime.utcfromtimestamp(entry["timestamp_sec"]).strftime("%H:%M:%S")
            log_lines.append(f"[{ts}] {entry['line']}")

        return "\n".join(log_lines)

    async def tail_logs(
        self,
        loki_label: str,
        since_ns: Optional[int] = None,
    ) -> list[dict]:
        """
        Poll for new log lines since `since_ns`.
        Returns only entries newer than since_ns.
        Used by the monitoring worker for incremental updates.
        """
        if since_ns is None:
            since_ns = int((time.time() - settings.LOKI_POLL_INTERVAL_SECONDS * 2) * 1e9)

        now_ns = int(time.time() * 1e9)
        return await self.query_logs(loki_label, limit=50, start_ns=since_ns, end_ns=now_ns)

    async def get_incident_logs(
        self,
        loki_label: str,
        incident_start_ts: float,
        limit: int = 100,
    ) -> list[dict]:
        """Get all logs for the duration of an incident."""
        start_ns = int(incident_start_ts * 1e9)
        end_ns = int(time.time() * 1e9)
        return await self.query_logs(loki_label, limit=limit, start_ns=start_ns, end_ns=end_ns)
