"""Trusted fixture bootstrap fails closed before native owners are loaded."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio.host.core.custody_registry import CustodyError, RegistryCustody
from studio.tests.godot import run_edit_publication_probe as probe


class FixtureSetupTests(unittest.TestCase):
    def test_missing_parent_setup_failure_precedes_native_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with patch.object(RegistryCustody, 'provision_base',
                              side_effect=CustodyError('CUSTODY_PROVISION_UNCERTAIN')):
                with patch.object(probe, 'load') as native:
                    with self.assertRaises(CustodyError):
                        probe.frozen(output, Path('unused.exe'), '0'*64, candidate_update=True)
            native.assert_not_called()
            self.assertFalse((output/'owned').exists())
            self.assertFalse((output/'custody-setup.json').exists())


if __name__ == '__main__':
    unittest.main()
