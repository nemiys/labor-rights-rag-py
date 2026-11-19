"""The in-memory limit on /ask, with a clock the tests move by hand."""

from labor_rights_rag.api.rate_limit import SlidingWindowLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_requests_up_to_the_limit_pass_then_the_next_one_waits() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60, clock=clock)

    assert limiter.check("1.2.3.4") == 0
    clock.now += 10
    assert limiter.check("1.2.3.4") == 0
    clock.now += 10
    assert limiter.check("1.2.3.4") == 40  # the first request leaves the window in 40 s


def test_a_request_is_allowed_again_once_the_oldest_leaves_the_window() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.check("1.2.3.4")

    clock.now += 60

    assert limiter.check("1.2.3.4") == 0


def test_a_refused_request_is_not_counted() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.check("1.2.3.4")
    for _ in range(5):
        limiter.check("1.2.3.4")  # hammering while refused

    clock.now += 60

    assert limiter.check("1.2.3.4") == 0


def test_each_client_has_its_own_allowance() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=FakeClock())
    limiter.check("1.2.3.4")

    assert limiter.check("5.6.7.8") == 0
