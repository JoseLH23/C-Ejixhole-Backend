"""Métricas de proceso sin cuerpos, parámetros ni datos personales."""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
import time


@dataclass(frozen=True)
class SloTargets:
    availability_percent: float = 99.5
    error_rate_percent: float = 1.0
    latency_p95_ms: int = 1000


class HttpMetricsRegistry:
    def __init__(self, *, sample_limit: int = 5000) -> None:
        self._lock = Lock()
        self._started_monotonic = time.monotonic()
        self._started_at = datetime.now(timezone.utc)
        self._requests = 0
        self._active = 0
        self._status_groups: Counter[str] = Counter()
        self._durations_ms: deque[int] = deque(maxlen=sample_limit)
        self._last_server_error_at: datetime | None = None

    def begin(self) -> None:
        with self._lock:
            self._active += 1

    def finish(self, status_code: int, duration_ms: int) -> None:
        group = f"{max(1, min(5, status_code // 100))}xx"
        with self._lock:
            self._active = max(0, self._active - 1)
            self._requests += 1
            self._status_groups[group] += 1
            self._durations_ms.append(max(0, duration_ms))
            if status_code >= 500:
                self._last_server_error_at = datetime.now(timezone.utc)

    @staticmethod
    def _percentile(values: list[int], percentile: float) -> int:
        if not values:
            return 0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
        return ordered[index]

    def snapshot(self, targets: SloTargets | None = None) -> dict:
        selected = targets or SloTargets()
        with self._lock:
            total = self._requests
            server_errors = self._status_groups.get("5xx", 0)
            durations = list(self._durations_ms)
            availability = ((total - server_errors) / total * 100) if total else 100.0
            error_rate = (server_errors / total * 100) if total else 0.0
            p50 = self._percentile(durations, 0.50)
            p95 = self._percentile(durations, 0.95)
            checks = {
                "availability": availability >= selected.availability_percent,
                "error_rate": error_rate <= selected.error_rate_percent,
                "latency_p95": p95 <= selected.latency_p95_ms,
            }
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "started_at": self._started_at.isoformat(),
                "uptime_seconds": int(time.monotonic() - self._started_monotonic),
                "requests": {
                    "total": total,
                    "active": self._active,
                    "by_status_group": dict(self._status_groups),
                    "server_errors": server_errors,
                },
                "latency_ms": {
                    "samples": len(durations),
                    "p50": p50,
                    "p95": p95,
                    "max": max(durations) if durations else 0,
                },
                "slo": {
                    "status": "healthy" if all(checks.values()) else "degraded",
                    "availability_percent": round(availability, 3),
                    "error_rate_percent": round(error_rate, 3),
                    "targets": {
                        "availability_percent": selected.availability_percent,
                        "error_rate_percent": selected.error_rate_percent,
                        "latency_p95_ms": selected.latency_p95_ms,
                    },
                    "checks": checks,
                },
                "last_server_error_at": (
                    self._last_server_error_at.isoformat() if self._last_server_error_at else None
                ),
            }


http_metrics = HttpMetricsRegistry()
