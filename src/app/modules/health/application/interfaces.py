from typing import Protocol


class HealthRepository(Protocol):
    async def ping(self) -> None: ...
