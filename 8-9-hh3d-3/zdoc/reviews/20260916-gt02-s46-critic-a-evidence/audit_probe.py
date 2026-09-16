"""Independently execute the reviewed coordinator verifier without writing its files."""
from pathlib import Path
import copy
import importlib.util
import json
from unittest import mock

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('coordinator_verifier',here.parent/'20260916-gt02-s46-audit/verify_evidence.py')
verifier=importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
normal=verifier.verify()
original=verifier.read
negatives=[]
for folder,filename in ((verifier.MANAGED,'managed-native-stdout.txt'),
                        (verifier.BOUNDARY,'native-stdout.txt'),
                        (verifier.REGISTRY,'registry-native-stdout.txt')):
    path=folder/filename
    for mode in ('wrong_digest','wrong_file','missing_map','missing_digest'):
        altered=copy.deepcopy(original(path))
        closure=altered['runtime_closure']
        if mode=='wrong_digest': closure['source_closure_sha256']='0'*64
        elif mode=='wrong_file': closure['files']['host/core/managed_service.py']='0'*64
        elif mode=='missing_map': del closure['files']
        else: del closure['source_closure_sha256']
        with mock.patch.object(verifier,'read',side_effect=lambda p:altered if p==path else original(p)):
            try: verifier.verify()
            except (AssertionError,KeyError): negatives.append({'lane':folder.parent.name,'case':mode,'rejected':True})
            else: raise AssertionError('native_binding_not_enforced')
assert verifier.verify()==normal
report={'normal':normal,'independent_negative_variants':negatives}
(here/'audit-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('CRITIC_A_AUDIT_COMPLETE '+json.dumps(report))
