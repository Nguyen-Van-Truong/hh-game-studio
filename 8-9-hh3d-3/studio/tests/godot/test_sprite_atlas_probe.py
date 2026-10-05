"""Reject frozen animation, wrong order, lost pause, and stale launch data."""
import copy
from datetime import datetime, timedelta, timezone
import unittest
from tests.godot.run_sprite_atlas_probe import preflight_valid, verify_samples


def trace():
    position = 0.0
    rows = []
    for tick in range(1, 101):
        active = not 38 <= tick <= 50
        if active:
            position = (position + 8/60) % 4
        frame = int(position)
        rows.append(dict(tick=tick, frame=frame, progress=position-frame,
                         delta=1/60, playing=(not 38 <= tick <= 49)))
    return rows


class SpriteAtlasProbeTests(unittest.TestCase):
    def test_8fps_loop_with_pause_and_resume(self):
        self.assertTrue(verify_samples(trace()))

    def test_no_false_pass_from_summary_or_subset(self):
        for value in ({'passed': True}, trace()[:-1], []):
            self.assertFalse(verify_samples(value))

    def test_stopped_skipped_wrong_speed_and_bool_frames_reject(self):
        changes = [lambda rows: rows[25].update(frame=(rows[24]['frame'] + 2) % 4),
                   lambda rows: rows[40].update(playing=True),
                   lambda rows: rows[40].update(progress=0.5),
                   lambda rows: rows[60].update(delta=1/30),
                   lambda rows: rows[60].update(frame=True),
                   lambda rows: rows[60].update(progress=float('nan'))]
        for change in changes:
            rows = trace()
            change(rows)
            self.assertFalse(verify_samples(rows))
        rows = trace()
        for row in rows:
            row.update(frame=0, progress=0)
        self.assertFalse(verify_samples(rows))

    def test_preflight_must_be_fresh_with_actual_resource_values(self):
        now = datetime.now(timezone.utc)
        value = dict(observed_utc=now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                     schema_id='hh-studio.benchmark-environment-preflight',
                     schema_version='1.2.0', foreign_engines=[],
                     available_memory_bytes=5*1024**3, commit_total_bytes=80,
                     commit_limit_bytes=100, **{'pass': True})
        self.assertTrue(preflight_valid(value))
        for changes in ({'available_memory_bytes': 1024}, {'commit_total_bytes': 86},
                        {'foreign_engines': [{'pid': 123}]}, {'pass': False},
                        {'observed_utc': (now-timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')}):
            changed = copy.deepcopy(value)
            changed.update(changes)
            self.assertFalse(preflight_valid(changed))


if __name__ == '__main__':
    unittest.main()
