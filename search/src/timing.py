"""Request timing helpers (logs only)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _round_s(value: float) -> float:
    return round(value, 3)


@dataclass
class RequestTiming:
    """Wall-clock timings from the start of an API request."""

    label: str
    started_at: float = field(default_factory=time.perf_counter)
    phases: dict[str, float] = field(default_factory=dict)
    extractions: list[dict[str, object]] = field(default_factory=list)

    def mark(self, name: str) -> None:
        self.phases[name] = time.perf_counter() - self.started_at
        logger.info(
            "[%s] phase %s at %.3fs",
            self.label,
            name,
            self.phases[name],
        )

    def record_extraction(
        self,
        *,
        href: str,
        total_s: float,
        fetch_s: float | None = None,
        llm_s: float | None = None,
        ok: bool = True,
    ) -> None:
        entry: dict[str, object] = {
            "href": href,
            "total_s": _round_s(total_s),
            "ok": ok,
        }
        if fetch_s is not None:
            entry["fetch_s"] = _round_s(fetch_s)
        if llm_s is not None:
            entry["llm_s"] = _round_s(llm_s)
        self.extractions.append(entry)
        logger.info(
            "[%s] extract %s: total=%.3fs fetch=%.3fs llm=%.3fs ok=%s",
            self.label,
            href,
            total_s,
            fetch_s or 0.0,
            llm_s or 0.0,
            ok,
        )

    def log_summary(self) -> None:
        total_s = time.perf_counter() - self.started_at
        extraction_total = sum(
            float(item.get("total_s", 0))
            for item in self.extractions
        )
        phases = ", ".join(f"{name}={value:.3f}s" for name, value in self.phases.items())
        logger.info(
            "[%s] done: total=%.3fs phases=[%s] extractions=%d extraction_total=%.3fs",
            self.label,
            total_s,
            phases,
            len(self.extractions),
            extraction_total,
        )
