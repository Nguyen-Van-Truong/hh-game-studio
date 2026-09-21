"""S143 bounded candidate preflight copied from the accepted preflight driver.

The candidate changes only verified_journal.py. This preflight runs the pinned
20-second import and two existing ten-command groups, keeps all original
cleanup/exit checks, and is explicitly excluded from F13/F14 and GT06 data.
"""
from pathlib import Path
import runpy

SOURCE = Path(__file__).resolve()
ORIGINAL = SOURCE.parents[1] / "20260919-gt06-s102-observability" / "preflight.py"
namespace = runpy.run_path(str(ORIGINAL), run_name="S143_CANDIDATE_PREFLIGHT")
namespace["RUN_ID"] = "gt06-s143-candidate-preflight-01"
namespace["BASE"] = SOURCE.parent
namespace["ROOT"] = SOURCE.parents[2]
namespace["__file__"] = str(SOURCE)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(SOURCE.parent))
    code = namespace["main"]()
    raise SystemExit(code)
