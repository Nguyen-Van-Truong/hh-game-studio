"""Verify portable integrity, optionally bind every view to retained local raw."""
from pathlib import Path
import argparse
import json
import os
import evidence_view as view

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
PACKAGES = {
    'scene': '20260917-gt04-s60-scene-01',
    'checkpoint': '20260917-gt04-s60-checkpoint-01',
    'export': '20260917-gt04-s60-export-01',
    'matrix': '20260917-gt04-s60-matrix',
    'file-audit': '20260917-gt04-s60-file-audit',
    'view-tests': 'gt04-s60-view-tests-01',
    'audit-tests': 'gt04-s60-audit-tests-01',
}


def verify(local=False):
    scrubber = view.PathView({'PROJECT': str(ROOT)}, forbidden_words=(os.environ.get('USERNAME', '__no_user__'),))
    results = {}
    for label, folder in PACKAGES.items():
        raw = ROOT / 'studio/.local/reviews' / folder
        results[label] = view.verify(HERE / 'portable' / label,
            raw_root=raw if local else None, scrubber=scrubber if local else None)
    return {'passed': True, 'local_raw_verified': local, 'formal_acceptance': False, 'packages': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-raw', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.local_raw)))
