"""Reuse the established plan checks without rewriting historical freeze files."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'20260911-r7'))
validator = importlib.import_module('validate_plans')
mutations = importlib.import_module('test_review_s19')

def main():
    manifest = validator.freeze('S20')
    inputs = {n:(validator.Z/n).read_bytes() for n in validator.NAMES}
    result = validator.validate(manifest, inputs, validator.Z)
    (HERE/'freeze-s20.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (HERE/'static-s20.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    original = mutations.manifest_for
    def manifest_s20(values):
        value = original(values)
        value['revision'] = 'S20'
        return value
    mutations.manifest_for = manifest_s20
    test = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(mutations.S19Tests))
    summary = {'result':result['result'], 'errors':result['errors'], 'warnings':result['warnings'],
               'mutation_tests':test.testsRun, 'failures':len(test.failures), 'errors_in_tests':len(test.errors),
               'manifest_sha256':manifest['manifest_sha256'],
               'validator_sha256':hashlib.sha256(Path(validator.__file__).read_bytes()).hexdigest(),
               'test_source_sha256':hashlib.sha256(Path(mutations.__file__).read_bytes()).hexdigest(),
               'limit':'Static inherited checks only; not design completeness/runtime/critic acceptance.'}
    (HERE/'selfcheck-s20.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary))
    return 0 if result['result'] == 'PASS_STATIC_ONLY' and test.wasSuccessful() else 1

if __name__ == '__main__':
    raise SystemExit(main())
