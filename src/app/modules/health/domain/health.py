from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatabaseHealthResult:
    is_up: bool
    detail: str | None = None
