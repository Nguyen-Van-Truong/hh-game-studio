"""Preserve compact, path-redacted coordinator experiment evidence."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import time

HERE = Path(__file__).resolve().parent
TRIAL = Path(os.environ['TEMP']) / 'hh3d-agentmemory-trial-20260911'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    reports = list(TRIAL.glob('probe-*/report.json'))
    if len(reports) != 1:
        raise ValueError('Choose exact trial; refusing ambiguous report')
    raw_path = reports[0]
    raw = json.loads(raw_path.read_text(encoding='utf-8'))
    expected = [0, 1, 2, 3, 4, 5]
    ids = [n['result']['memory']['id'] for n in raw['notes']]
    top1 = [q['result']['results'][0]['obsId'] == ids[index]
            for q, index in zip(raw['queries'][:6], expected)]
    repeated = [r['ms'] for r in raw['requests'] if r['route'] == 'search' and r['query'] == 'Godot'][-11:-1]
    baseline_path = raw_path.parent / 'curated-notes.json'
    baseline_path.write_text(json.dumps([n['text'] for n in raw['notes']], ensure_ascii=False, indent=2), encoding='utf-8')
    baseline = []
    for q in raw['queries']:
        before = time.perf_counter()
        result = subprocess.run(['rg', '-i', '-F', '--', q['query'], str(baseline_path)], capture_output=True, timeout=5)
        baseline.append({'query': q['query'], 'host_ms': (time.perf_counter()-before)*1000,
                         'exit': result.returncode, 'response_bytes': len(result.stdout)})
    summary = {
        'status': 'RETRIEVAL_SMOKE_PASS' if all(top1) else 'GAP',
        'package': '@agentmemory/agentmemory@0.9.29', 'engine_image': raw['image'],
        'authority_sha256_at_trial': raw['authority_sha256'],
        'mode': 'full server; noop LLM; no embedding provider; manual REST recall; no client hooks/MCP integration',
        'queries_top1_passed': sum(top1), 'queries_tested': len(top1),
        'absent_keyword_empty': raw['queries'][-1]['result']['results'] == [],
        'empty_control_project_returned_no_rows': raw['scope_b']['results'] == [],
        'restart_ids_stable': raw['restart']['results'] == raw['before_restart']['results'],
        'warm_recall_ms': {'samples': len(repeated), 'median': statistics.median(repeated), 'max': max(repeated)},
        'engine_container_resource_sample': raw['resource_sample'],
        'resource_limitations': 'Engine container only. Host Node, Docker Desktop/VM and model context excluded; not total RAM.',
        'data_bytes': raw['data_bytes'], 'trial_duration_seconds': raw['elapsed_seconds'],
        'container_stopped': raw['container_final'] == 'false',
        'raw_report_sha256': sha(raw_path), 'probe_sha256': sha(TRIAL/'coordinator-probe.py'),
        'token_savings': None, 'coding_quality': 'NOT_MEASURED',
        'baseline': baseline,
        'baseline_limitations': 'Six curated notes; rg includes subprocess startup, REST measures a warm service. Not equivalent coding-task or total-cost benchmark.',
        'decision': 'Keep experimental and off when idle. Use curated source-linked notes by default; no evidence memory is cheapest. Broader rollout requires measured successful-task cost and stale/conflicting populated-project cases.',
        'findings': [
            'Native Windows installer does not auto-install iii; download attempt timed out before archive existed, not checksum mismatch.',
            'Default Docker demo ignored requested relocated ports and failed Node exec watcher startup; replaced only in isolated coordinator diagnostic.',
            'Default launcher wrote user .agentmemory/engine-state.json; exact trial marker moved to TEMP, default trial container stopped.',
            'Standalone MCP fallback uses substring matching, not full BM25; not used as BM25 evidence.',
            'All notes share source filename; Godot search returned irrelevant lower-ranked rows. Top1 was correct; top3 precision is not perfect.',
            'No permanent hooks, Codex/Grok global config changes, transcript import or API keys used.',
            'Short keyword smoke is not proof of cross-project authorization, stale-memory safety, multilingual semantic quality or quota saving.'
        ],
    }
    (HERE/'memory-result.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    portable = dict(raw)
    portable.pop('container_id', None)
    portable.pop('node_pids', None)
    (HERE/'memory-runtime.json').write_text(json.dumps(portable, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    # Reference script stays local: absolute machine paths; not a portable product tool.
    shutil.copy2(TRIAL/'coordinator-probe.py', HERE/'memory-probe.local.py')
    for role in ['canary','runner-admission','bootstrap-offline','memory-trial','version-check','version-repair']:
        batchfile = HERE/(role+'-batch.local.json')
        if not batchfile.exists():
            continue
        batch = json.loads(batchfile.read_text(encoding='utf-8-sig'))
        attempt = Path(batch['jobs'][0]['attempt_dir'])
        meta = attempt/'runner-meta.json'
        record = {'role':role, 'session':batch['jobs'][0]['session'], 'model':batch['model'], 'effort':batch['reasoning_effort'], 'polls_used':batch['polls_used'], 'artifact_hashes':[]}
        if meta.exists():
            record['terminal'] = json.loads(meta.read_text(encoding='utf-8-sig'))
        for name in ['events.jsonl','stderr.txt','config.json','TASK.txt','workspace/response.txt','coordinator-review.json','coordinator-review-2.json']:
            path = attempt/name
            if path.is_file():
                record['artifact_hashes'].append({'path':name,'sha256':sha(path),'bytes':path.stat().st_size})
        (HERE/(role+'-receipt.json')).write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True))

if __name__ == '__main__':
    main()
