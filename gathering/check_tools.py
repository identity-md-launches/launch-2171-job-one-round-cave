#!/usr/bin/env python3
"""Run the reviewed offline checks, keeping upstream temporary fixtures in scratch."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    scratch = ROOT / "test/scratch/time-flint"
    scratch.mkdir(parents=True, exist_ok=True)
    # The upstream suite creates fixtures beside __file__. Copy its exact bytes
    # so running it never creates, deletes or changes files inside a line.
    for name in ("time_flint.py", "test_time_flint.py"):
        shutil.copyfile(ROOT / "line-3/tools/time-flint" / name, scratch / name)
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for n in range(1, 5) for p in (ROOT / f"line-{n}").rglob("*") if p.is_file()}
    suites = ["line-1/tools/paired-verdict", "line-1/tools/candidate-ladder",
              "line-1/tools/paired-power", "line-2/tools/unicode-lantern",
              "line-2/tools/json-lantern", "test/scratch/time-flint", "line-3/tools/timeline-replay",
              "line-4/tools/unit-flint", "gathering", "shared/reviewed-timeline", "shared/replay-review"]
    checks = []
    for suite in suites:
        command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", suite, "-v"]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        match = re.search(r"Ran (\d+) tests?", run.stderr)
        checks.append({"suite": suite, "tests": int(match[1]) if match else 0,
                       "exit_code": run.returncode})
        if run.returncode:
            print(run.stderr, file=sys.stderr)
    scans = []
    for source in ("line-1/tools/paired-verdict/paired_verdict.py",
                   "line-1/tools/candidate-ladder/candidate_ladder.py",
                   "line-1/tools/paired-power/paired_power.py",
                   "line-2/tools/json-lantern/json_lantern.py",
                   "line-3/tools/timeline-replay/timeline_replay.py",
                   "line-2/tools/unicode-lantern/unicode_lantern.py",
                   "line-3/tools/time-flint/time_flint.py",
                   "line-4/tools/unit-flint/unit_flint.py"):
        run = subprocess.run([sys.executable, "-B", "line-2/tools/unicode-lantern/unicode_lantern.py",
                              "--file", source], cwd=ROOT, capture_output=True, text=True)
        result = json.loads(run.stdout)
        scans.append({"source": source, "exit_code": run.returncode,
                      **{k: result[k] for k in ("sha256", "bytes", "finding_count", "unicode_version")}})
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
             for n in range(1, 5) for p in (ROOT / f"line-{n}").rglob("*") if p.is_file()}
    unchanged = before == after
    success = unchanged and all(c["exit_code"] == 0 for c in checks + scans) and all(c["tests"] > 0 for c in checks)
    print(json.dumps({"checks_passed": success, "suites": checks, "source_scans": scans,
                      "test_count": sum(c["tests"] for c in checks),
                      "line_files_unchanged": unchanged, "line_file_count": len(before),
                      "line_3_fixture_note": "Unmodified source and suite copied to test/scratch/time-flint before discovery."},
                     indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
