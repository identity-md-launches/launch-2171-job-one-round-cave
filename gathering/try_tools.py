#!/usr/bin/env python3
"""Run bounded documented CLI examples and preserve compact observed results."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
CASES = [
 ('paired verdict demo', ['line-1/tools/paired-verdict/paired_verdict.py', '--demo'], 0),
 ('paired verdict CSV', ['line-1/tools/paired-verdict/paired_verdict.py', '--input', 'line-1/tools/paired-verdict/example.csv'], 0),
 ('candidate ladder', ['line-1/tools/candidate-ladder/candidate_ladder.py', '--demo'], 0),
 ('prospective power', ['line-1/tools/paired-power/paired_power.py', '--demo'], 0),
 ('raw Unicode', ['line-2/tools/unicode-lantern/unicode_lantern.py', '--demo'], 0),
 ('decoded JSON', ['line-2/tools/json-lantern/json_lantern.py', '--demo'], 0),
 ('actual record JSON', ['line-2/tools/json-lantern/json_lantern.py', '--file', 'dist/line-2/22.json'], 0),
 ('timeline demo', ['line-3/tools/time-flint/time_flint.py', '--demo', '--json'], 0),
 ('timeline supplied fixtures', ['line-3/tools/time-flint/time_flint.py', '--json', '--clock-uncertainty-ms', '750', 'line-3/tools/time-flint/examples/client.txt', 'line-3/tools/time-flint/examples/server.jsonl'], 0),
 ('timeline replay', ['line-3/tools/timeline-replay/timeline_replay.py', 'demo'], 0),
 ('exact distance', ['line-4/tools/unit-flint/unit_flint.py', '1.5 km + 350 m', '--to', 'm', '--json'], 0),
 ('exact matching claim', ['line-4/tools/unit-flint/unit_flint.py', '10 km / 2 h', '--expect', '5 km/h', '--to', 'm/s', '--json'], 0),
 ('exact mismatching claim', ['line-4/tools/unit-flint/unit_flint.py', '10 km / 2 h', '--expect', '6 km/h', '--to', 'm/s', '--json'], 1),
 ('invalid dimension claim', ['line-4/tools/unit-flint/unit_flint.py', '0 m', '--expect', '0 s', '--json'], 2),
 ('shared reviewed timeline', ['shared/reviewed-timeline/reviewed_timeline.py', '--demo', '--clock-bound', '0.75 s'], 0),
 ('shared replay review', ['shared/replay-review/replay_review.py', 'demo'], 0),
]


def main():
    results = []
    for name, args, expected in CASES:
        command = [sys.executable, '-B', *args]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
        row = {'name': name, 'command': ['python3', '-B', *args],
               'expected_exit': expected, 'exit_code': run.returncode,
               'passed': run.returncode == expected}
        if run.stdout:
            value = json.loads(run.stdout)
            # Small numeric/evidence summaries; full reports are reproducible.
            keys = ['paired_cases', 'table', 'test', 'candidates', 'comparison_threshold',
                    'smallest_evaluated_size_meeting_target', 'sizes', 'finding_count',
                    'assessment', 'sha256', 'value', 'unit', 'check', 'replay',
                    'tampered_report_rejected', 'tampered_timeline_rejected', 'review_errors',
                    'json_lines_checked', 'digest_pin_checked']
            row['observed'] = {k: value[k] for k in keys if k in value}
            if 'events' in value:
                row['observed'].update(events=len(value['events']), omitted=len(value['omitted']),
                                       overlap_groups=[e['overlap_group'] for e in value['events']])
        if run.stderr:
            row['diagnostic'] = run.stderr[:2000]
        results.append(row)
    result = {'checks_passed': all(r['passed'] for r in results),
              'examples': results, 'note': 'Demos and fixtures are synthetic; the actual record scan checks real workspace bytes. No live system performance or incident is claimed.'}
    print(json.dumps(result, indent=2))
    return 0 if result['checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
