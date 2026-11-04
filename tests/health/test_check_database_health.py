import asyncio

from customer_support_agent.modules.health.application.check_database_health import (
    CheckDatabaseHealthUseCase,
)


class FakeRepository:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.error = error
        self.delay = delay

    async def ping(self) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error


async def test_returns_up_when_repository_succeeds() -> None:
    use_case = CheckDatabaseHealthUseCase(FakeRepository(), timeout=1.0)

    result = await use_case.execute()

    assert result.is_up is True
    assert result.detail is None


async def test_returns_down_with_detail_when_repository_fails() -> None:
    use_case = CheckDatabaseHealthUseCase(
        FakeRepository(error=RuntimeError("boom")),
        timeout=1.0,
    )

    result = await use_case.execute()

    assert result.is_up is False
    assert result.detail == "RuntimeError: boom"


async def test_returns_down_when_check_times_out() -> None:
    use_case = CheckDatabaseHealthUseCase(
        FakeRepository(delay=1.0),
        timeout=0.01,
    )

    result = await use_case.execute()

    assert result.is_up is False
    assert result.detail is not None
