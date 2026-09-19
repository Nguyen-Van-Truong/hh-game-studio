"""One no-engine owned probe; retain exact failed configure locals, no bypass."""
from pathlib import Path
import ctypes
import hashlib
import importlib.util
import json
import sys
import time
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def fields(value):
    return {'flags': int(value.basic.flags), 'active_limit': int(value.basic.active_limit),
            'job_time': int(value.basic.job_time), 'job_memory': int(value.job_memory)}


def main():
    assert len(sys.argv) == 2 and sys.argv[1] in ('direct-01', 'launcher-01')
    output = BASE / ('job-probe-' + sys.argv[1])
    output.mkdir(exist_ok=False)
    support = ROOT / 'zdoc/reviews/20260919-gt06-s102-observability/preflight.py'
    spec = importlib.util.spec_from_file_location('s117_support', support)
    util = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(util)
    campaign, _, _, sources = util.load_campaign(ROOT)
    from studio.tests.replay import benchmark_job as job_module
    execution = {'studio/' + name: digest for name, digest in sources.items()}
    for path in (Path(__file__), support):
        execution[path.relative_to(ROOT).as_posix()] = util.sha(path)
    util.write(output / 'freeze.json', {'execution': execution,
        'source_closure': campaign.closure(sources), 'formal_acceptance': False,
        'engine_runs': 0, 'operation': 'original BenchmarkProcess running only Python pass'})
    original, observed, errors, owner, capture = job_module.configure, [], [], None, None

    def configure(job, *, campaign_host=False):
        try:
            result = original(job, campaign_host=campaign_host)
            observed.append({'original_return': result})
            return result
        except BaseException as error:
            trace = error.__traceback__
            while trace:
                if trace.tb_frame.f_code is original.__code__:
                    local = trace.tb_frame.f_locals
                    if all(k in local for k in ('limits', 'observed', 'size')):
                        observed.append({'requested': fields(local['limits']),
                            'observed': fields(local['observed']),
                            'returned_size': local['size'].value,
                            'expected_size': ctypes.sizeof(local['observed'])})
                trace = trace.tb_next
            raise

    started = time.monotonic()
    try:
        with patch.object(job_module, 'configure', configure):
            owner = campaign.BenchmarkProcess([sys.executable, '-B', '-c', 'pass'],
                cwd=output, output=output/'owned', source_root=ROOT,
                source_files=execution, binary_sha256=util.sha(Path(sys.executable)),
                campaign_host=True)
            while owner.tick() is None:
                util.need(time.monotonic() - started < 15, 'S117_JOB_PROBE_TIMEOUT')
                time.sleep(.05)
            capture = owner.finish()
    except BaseException as error:
        errors.append(('probe', error))
        if owner is None:
            owner = getattr(error, 'cleanup_owner', None)
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                errors.append(('cleanup', error))
        result = {'formal_acceptance': False, 'engine_runs': 0,
            'configure': observed, 'errors': util.errors_record(errors),
            'capture': capture, 'owner': campaign._editor_cleanup_state(owner),
            'actual_target': campaign._target_exit_state(output, 'owned'),
            'source_unchanged': campaign.source_files() == sources,
            'elapsed_seconds': time.monotonic()-started}
        util.write(output/'result.json', result)
        print(json.dumps({'configure': observed, 'errors': util.errors_record(errors),
            'owner': result['owner'], 'actual_target': result['actual_target']}))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
