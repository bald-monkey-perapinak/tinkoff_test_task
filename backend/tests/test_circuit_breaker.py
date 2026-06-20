import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    @pytest.fixture
    def breaker(self):
        return CircuitBreaker("test", fail_threshold=3, recovery_timeout=1)

    async def test_starts_closed(self, breaker):
        assert await breaker.call_allowed()
        assert breaker.get_state()["state"] == "closed"

    async def test_opens_after_threshold(self, breaker):
        for _ in range(3):
            await breaker.record_failure()
        assert not await breaker.call_allowed()
        assert breaker.get_state()["state"] == "open"

    async def test_transitions_to_half_open(self, breaker):
        for _ in range(3):
            await breaker.record_failure()
        assert breaker.get_state()["state"] == "open"
        await asyncio.sleep(1.1)
        assert await breaker.call_allowed()
        assert breaker.get_state()["state"] == "half_open"

    async def test_closes_after_success_in_half_open(self, breaker):
        for _ in range(3):
            await breaker.record_failure()
        await asyncio.sleep(1.1)
        await breaker.call_allowed()
        await breaker.record_success()
        assert breaker.get_state()["state"] == "closed"
        assert breaker.get_state()["fail_count"] == 0

    async def test_stays_open_on_failure_in_half_open(self, breaker):
        for _ in range(3):
            await breaker.record_failure()
        await asyncio.sleep(1.1)
        await breaker.call_allowed()
        await breaker.record_failure()
        assert breaker.get_state()["state"] == "open"

    async def test_success_resets_fail_count(self, breaker):
        await breaker.record_failure()
        await breaker.record_failure()
        await breaker.record_success()
        assert breaker.get_state()["fail_count"] == 0

    async def test_does_not_open_below_threshold(self, breaker):
        for _ in range(2):
            await breaker.record_failure()
        assert await breaker.call_allowed()
        assert breaker.get_state()["state"] == "closed"
