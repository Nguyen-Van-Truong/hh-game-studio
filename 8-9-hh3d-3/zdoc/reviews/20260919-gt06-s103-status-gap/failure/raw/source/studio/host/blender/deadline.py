"""Original absolute deadline with a monotonic, non-renewable local budget."""
import math
import time


class DeadlineError(ValueError):
    def __init__(self, code):
        self.code = code
        self.outcome_unknown = False
        super().__init__(code)


class AbsoluteDeadline:
    def __init__(self, deadline_ms, *, host_deadline=None):
        self.deadline_ms = deadline_ms
        self.monotonic_end = None
        if deadline_ms is None:
            return
        if type(deadline_ms) is not int or not 1 <= deadline_ms < 2**53:
            raise DeadlineError('BLENDER_ABSOLUTE_DEADLINE_LIMIT')
        if type(host_deadline) not in (int, float) or not math.isfinite(host_deadline):
            raise DeadlineError('BLENDER_OWNER_DEADLINE_REQUIRED')
        now = time.monotonic()
        self.monotonic_end = min(host_deadline, now + (deadline_ms - int(time.time() * 1000)) / 1000)

    def check(self):
        if self.deadline_ms is not None and (time.monotonic() >= self.monotonic_end
                or int(time.time() * 1000) >= self.deadline_ms):
            raise DeadlineError('BLENDER_DEADLINE_EXPIRED')
