from pathlib import Path
import importlib.util
import json
import sys

here=Path(__file__).resolve().parent
product=here.parents[2]
spec=importlib.util.spec_from_file_location('owned_runner',product/'studio/build/bootstrap/run_fixture.py')
runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
report=runner.run_process([sys.executable,'-B',str(here/'review_probe.py')],cwd=product,
    output=here,timeout=120,label='critic-a')
(here/'capture.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
sys.exit(0 if report['exit_code']==0 and report['tree_verified'] and not report['timed_out'] else 1)
