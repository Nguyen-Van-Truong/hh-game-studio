"""Review-only regression tests for the S157 candidate safety boundary."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
S157 = HERE.parent / "20260922-gt06-s157-launcher"
ATTR = HERE.parent / "20260922-gt06-s157-attribution"
sys.path.insert(0, str(HERE))
import s158_hardening_guard as guard


class S158HardeningTests(unittest.TestCase):
    def test_launcher_is_blocked_until_helper_and_prefix_are_bound(self):
        result = guard.audit_launcher(S157 / "diagnostic_launcher_s157.py")
        codes = {item["code"] for item in result["findings"]}
        self.assertFalse(result["eligible_to_dispatch"])
        self.assertIn("HELPER_NOT_PINNED", codes)
        self.assertIn("SUMMARY_PREFIX_PID_NOT_BOUND", codes)
        self.assertIn("BOUNDARY_PREFIX_NOT_REQUIRED", codes)

    def test_reserved_pss_fields_block_temporal_attribution(self):
        result = guard.audit_attribution_spec(ATTR / "diagnostic-spec.json")
        self.assertFalse(result["eligible_to_dispatch"])
        self.assertIn("creation_time_filetime", result["reserved_fields"])
        self.assertIn("granted_access", result["reserved_fields"])


if __name__ == "__main__":
    unittest.main()
