"""The native registry lane must reject stale or incomplete frozen-source binding."""
import copy
import json
from pathlib import Path
from unittest import mock
import verify_evidence as verify

original = verify.read
results = []
for folder in (verify.NATIVE,):
    path = folder/'registry-native-stdout.txt'
    native = original(path)
    for case in ('stale_closure', 'file_changed_digest_retained', 'map_missing', 'digest_missing'):
        corrupt = copy.deepcopy(native)
        if case == 'stale_closure':
            corrupt['runtime_closure']['source_closure_sha256'] = '0' * 64
        elif case == 'file_changed_digest_retained':
            corrupt['runtime_closure']['files']['host/core/custody_registry.py'] = '0' * 64
        elif case == 'map_missing':
            del corrupt['runtime_closure']['files']
        else:
            del corrupt['runtime_closure']['source_closure_sha256']
        with mock.patch.object(verify, 'read', side_effect=lambda p: corrupt if p == path else original(p)):
            try:
                verify.verify()
            except (AssertionError, KeyError):
                results.append({'lane': folder.parent.name, 'case': case, 'rejected': True})
            else:
                raise RuntimeError('VERIFIER_ADMITTED_' + case)
normal = verify.verify()
record = {'native_binding_regressions': results, 'normal_status': normal['status'],
          'source_closure': normal['source_closure_sha256']}
Path(__file__).with_name('native-binding-regression.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
print(json.dumps(record))
