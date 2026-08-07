import asyncio
import time
from collections import deque


class SlidingWindowLimiter:
    """In-memory sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def seconds_until_allowed(self) -> float:
        async with self._lock:
            now = time.monotonic()
            self._prune(now)
            if len(self._events) < self.max_requests:
                return 0.0
            return max(0.0, self._events[0] + self.window_seconds - now)

    async def record(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._prune(now)
            self._events.append(now)

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._events and self._events[0] <= cutoff:
            self._events.popleft()


class GeminiRateLimiter:
    """Strict free-tier limits: global + per-user RPM, daily cap, min interval."""

    def __init__(
        self,
        user_rpm: int,
        user_daily: int,
        global_rpm: int,
        min_interval: float,
    ):
        self.user_rpm = user_rpm
        self.user_daily = user_daily
        self.global_rpm = global_rpm
        self.min_interval = min_interval
        self._global = SlidingWindowLimiter(global_rpm, 60.0)
        self._user_minute: dict[str, SlidingWindowLimiter] = {}
        self._user_daily: dict[str, SlidingWindowLimiter] = {}
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _user_limiter(self, store: dict[str, SlidingWindowLimiter], user_id: str, max_req: int, window: float) -> SlidingWindowLimiter:
        if user_id not in store:
            store[user_id] = SlidingWindowLimiter(max_req, window)
        return store[user_id]

    async def check(self, user_id: str) -> tuple[bool, str, float]:
        """Return (allowed, message, wait_seconds)."""
        async with self._lock:
            now = time.monotonic()
            last = self._last_request.get(user_id, 0.0)
            interval_wait = self.min_interval - (now - last)
            if interval_wait > 0:
                return False, f"Please wait {interval_wait:.0f}s between messages (free tier limit).", interval_wait

        global_wait = await self._global.seconds_until_allowed()
        if global_wait > 0:
            return False, f"System busy — retry in {global_wait:.0f}s (free tier rate limit).", global_wait

        user_minute = self._user_limiter(self._user_minute, user_id, self.user_rpm, 60.0)
        user_wait = await user_minute.seconds_until_allowed()
        if user_wait > 0:
            return False, f"Too many messages — retry in {user_wait:.0f}s (max {self.user_rpm}/min).", user_wait

        user_day = self._user_limiter(self._user_daily, user_id, self.user_daily, 86400.0)
        daily_wait = await user_day.seconds_until_allowed()
        if daily_wait > 0:
            return False, f"Daily limit reached ({self.user_daily} messages/day). Try again tomorrow.", daily_wait

        return True, "", 0.0

    async def record(self, user_id: str) -> None:
        async with self._lock:
            self._last_request[user_id] = time.monotonic()
        await self._global.record()
        await self._user_limiter(self._user_minute, user_id, self.user_rpm, 60.0).record()
        await self._user_limiter(self._user_daily, user_id, self.user_daily, 86400.0).record()
