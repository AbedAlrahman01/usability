from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class GlobalFilterState:
    start_date: date | None = None
    end_date: date | None = None
    month: list[str] = field(default_factory=list)
    weekday: list[str] = field(default_factory=list)
    airline: list[str] = field(default_factory=list)
    origin: list[str] = field(default_factory=list)
    dest: list[str] = field(default_factory=list)
    route: list[str] = field(default_factory=list)
    delay_threshold: int = 0
    cancelled: str = "All"
    diverted: str = "All"
    distance_group: list[str] = field(default_factory=list)
    time_of_day_group: list[str] = field(default_factory=list)

    def active_label(self) -> str:
        parts: list[str] = []
        if self.start_date and self.end_date:
            parts.append(f"from {self.start_date.isoformat()} to {self.end_date.isoformat()}")
        if self.airline:
            parts.append("airlines " + ", ".join(self.airline[:3]) + ("..." if len(self.airline) > 3 else ""))
        if self.origin:
            parts.append("origin " + ", ".join(self.origin[:3]) + ("..." if len(self.origin) > 3 else ""))
        if self.dest:
            parts.append("destination " + ", ".join(self.dest[:3]) + ("..." if len(self.dest) > 3 else ""))
        if self.route:
            parts.append("routes " + ", ".join(self.route[:2]) + ("..." if len(self.route) > 2 else ""))
        if self.delay_threshold:
            parts.append(f"delay threshold >= {self.delay_threshold} min")
        if self.cancelled != "All":
            parts.append(f"cancelled: {self.cancelled.lower()}")
        if self.diverted != "All":
            parts.append(f"diverted: {self.diverted.lower()}")
        if self.distance_group:
            parts.append("distance " + ", ".join(self.distance_group))
        if self.time_of_day_group:
            parts.append("time of day " + ", ".join(self.time_of_day_group))
        return "Showing all Q1 2024 flights." if not parts else "Showing flights " + ", ".join(parts) + "."

