"""Exercise registrar validation through PowerShell; never register a task.

The dry-run receipts below are synthetic test fixtures, not native readiness proof.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import arm_formal_window as arm


@unittest.skipUnless(os.name == 'nt', 'Windows registrar')
class RegistrarValidationTests(unittest.TestCase):
    def test_validate_only_and_reject_invalid_binding_without_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / 'request.json'
            start = datetime.now(timezone.utc) + timedelta(hours=1)
            config = {'campaign_id': 'gt06-o4-formal-98', 'start': start.isoformat(),
                      'end': (start + timedelta(hours=4)).isoformat(),
                      'source': 'a' * 64, 'profile': arm.PROFILE,
                      'arm_sha256': hashlib.sha256(arm.HERE.read_bytes()).hexdigest()}
            request.write_text(json.dumps(config), encoding='utf-8')
            marker = root / 'dry-run-success.json'
            receipt = {'schema': 'HH-GT06-ARM-DRY-RUN-1', 'campaign_id': config['campaign_id'],
                       'request_sha256': hashlib.sha256(request.read_bytes()).hexdigest(),
                       'arm_sha256': config['arm_sha256'], 'decision': 'BEFORE_WINDOW',
                       'observed_at': datetime.now(timezone.utc).isoformat()}
            command = [str(arm.POWERSHELL), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                       '-File', str(arm.HERE.with_name('register_formal09_arm.ps1')),
                       '-RequestPath', str(request), '-ValidateOnly']

            def invoke(extra=()):
                before = {p.name: p.read_bytes() for p in root.iterdir()}
                result = subprocess.run([*command, *extra], capture_output=True, timeout=20,
                                        creationflags=0x08000000)
                self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
                return result

            self.assertNotEqual(invoke().returncode, 0)  # Mandatory successful dry-run missing.
            marker.write_text(json.dumps(receipt), encoding='utf-8')
            valid = invoke()
            self.assertEqual(valid.returncode, 0, valid.stderr.decode(errors='replace'))
            self.assertEqual(json.loads(valid.stdout.decode('utf-8-sig'))['arm_task_name'], arm.arm_task_name(config))
            wrong_name = invoke(['-TaskName', 'HHStudio.GT06.arm-formal99-20261002'])
            self.assertNotEqual(wrong_name.returncode, 0)
            self.assertIn(b'ARM_TASK_NAME_BINDING', wrong_name.stderr)
            request.write_bytes(request.read_bytes() + b'\n')
            self.assertNotEqual(invoke().returncode, 0)  # Receipt is bound to exact request bytes.


if __name__ == '__main__':
    unittest.main()
