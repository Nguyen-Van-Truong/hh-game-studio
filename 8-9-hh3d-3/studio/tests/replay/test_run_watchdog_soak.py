import unittest

from studio.tests.replay import run_watchdog_soak as soak


class WatchdogSoakManifestTests(unittest.TestCase):
    def test_manifest_uses_campaign_import_closure_and_entrypoint(self):
        files = soak.source_manifest()
        self.assertIn('tests/replay/benchmark_docker_inventory.py', files)
        self.assertIn('tests/replay/run_watchdog_soak.py', files)
        self.assertIn('tests/replay/run_benchmark_campaign.py', files)
        self.assertEqual(files, dict(sorted(files.items())))


if __name__ == '__main__':
    unittest.main()
