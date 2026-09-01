"""
Prometheus HTTP API client.
Handles metric queries for the monitoring worker and incident context building.
"""
import time
from typing import Optional
import aiohttp
from app.config import get_settings

settings = get_settings()


class PrometheusClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.PROMETHEUS_URL).rstrip("/")

    async def query_instant(self, query: str) -> list[dict]:
        """Execute an instant PromQL query."""
        url = f"{self.base_url}/api/v1/query"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"query": query}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("data", {}).get("result", [])

    async def query_range(
        self,
        query: str,
        start: Optional[float] = None,
        end: Optional[float] = None,
        step: int = 30,
    ) -> list[dict]:
        """
        Execute a range PromQL query.
        Returns list of {metric: {labels}, values: [[ts, val], ...]}
        """
        now = time.time()
        if end is None:
            end = now
        if start is None:
            start = now - settings.PROMETHEUS_LOOKBACK_MINUTES * 60

        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("data", {}).get("result", [])

    async def get_cpu_timeseries(
        self,
        prom_label: str,
        lookback_minutes: Optional[int] = None,
        step: int = 30,
    ) -> tuple[list[float], list[float]]:
        """
        Query CPU utilization for a target.
        Returns (timestamps, cpu_percentages).

        Uses node_exporter style: 100 - (avg iowait/idle)
        """
        lookback = lookback_minutes or settings.PROMETHEUS_LOOKBACK_MINUTES
        query = (
            f'100 - (avg by(instance) (rate(node_cpu_seconds_total{{mode="idle",{prom_label}}}[2m])) * 100)'
        )
        results = await self.query_range(query, start=time.time() - lookback * 60, step=step)

        if not results:
            return [], []

        # Take the first result series
        series = results[0].get("values", [])
        timestamps = [float(v[0]) for v in series]
        values = [float(v[1]) for v in series]
        return timestamps, values

    async def get_disk_usage(self, prom_label: str) -> Optional[float]:
        """Get current disk usage percentage for a target."""
        query = f'100 - (node_filesystem_avail_bytes{{{prom_label},mountpoint="/"}}) / node_filesystem_size_bytes{{{prom_label},mountpoint="/"}} * 100'
        results = await self.query_instant(query)
        if results:
            return float(results[0]["value"][1])
        return None

    async def get_current_cpu(self, prom_label: str) -> Optional[float]:
        """Get current CPU% for a target."""
        query = f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle",{prom_label}}}[1m])) * 100)'
        results = await self.query_instant(query)
        if results:
            return float(results[0]["value"][1])
        return None

    async def get_context_metrics_table(
        self, prom_label: str, lookback_minutes: int = 30
    ) -> str:
        """
        Build a human-readable metrics table for LLM context injection.
        Returns a text table of recent metric snapshots.
        """
        timestamps, values = await self.get_cpu_timeseries(prom_label, lookback_minutes=lookback_minutes, step=60)
        if not timestamps:
            return "No Prometheus data available for this target."

        lines = ["Timestamp (UTC)          | CPU %"]
        lines.append("-" * 40)
        import datetime
        for ts, val in zip(timestamps[-30:], values[-30:]):  # Last 30 points
            dt = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"{dt} | {val:.2f}%")

        return "\n".join(lines)

    async def get_all_targets_current_metrics(self) -> list[dict]:
        """
        Broad query: get current CPU% for all monitored instances.
        Returns list of {instance, cpu_percent}.
        """
        query = '100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)'
        results = await self.query_instant(query)
        out = []
        for r in results:
            instance = r.get("metric", {}).get("instance", "unknown")
            val = float(r["value"][1]) if r.get("value") else 0.0
            out.append({"instance": instance, "cpu_percent": val})
        return out
