"""Verifier-only regressions: reject stale, absent and mismatched native maps."""
import copy
import json
from pathlib import Path
from unittest import mock
import verify_evidence as verify

original = verify.read
native_path = verify.ROOT / 'zdoc/reviews/20260916-gt02-s43-native/run-01.stdout.json'
native = original(native_path)
results = []
for case in ('stale_closure', 'file_changed_digest_retained', 'map_missing', 'digest_missing'):
    corrupt = copy.deepcopy(native)
    if case == 'stale_closure':
        corrupt['runtime_closure']['source_closure_sha256'] = '6972f55fbc72e3095ef4869c69428b89c5aea68ca24532a96d174dbc2c33131f'
    elif case == 'file_changed_digest_retained':
        corrupt['runtime_closure']['files']['host/core/safe_create.py'] = '0' * 64
    elif case == 'map_missing':
        del corrupt['runtime_closure']['files']
    else:
        del corrupt['runtime_closure']['source_closure_sha256']
    with mock.patch.object(verify, 'read', side_effect=lambda path: corrupt if path == native_path else original(path)):
        try:
            verify.verify()
        except (AssertionError, KeyError):
            results.append({'case': case, 'rejected': True})
        else:
            raise RuntimeError('VERIFIER_ADMITTED_' + case)
normal = verify.verify()
record = {'native_binding_regressions': results, 'normal_status': normal['status'], 'source_closure': normal['source_closure_sha256']}
Path(__file__).with_name('native-binding-regression.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
print(json.dumps(record))
