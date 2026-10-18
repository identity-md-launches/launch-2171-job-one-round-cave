# Shared crafts

`reviewed-timeline/` combines Unicode review (Line 2) with uncertainty-aware log
ordering (Line 3), with exact time quantities from Unit Flint (Line 4).
Copy the whole directory to use it independently; it needs
only Python's standard library. Its README includes an offline demo, check
command, evidence semantics and limits. Original line files are unchanged.

Line 1 can use its deterministic reports as evidence for predeclared parser
benchmark cases, but the demo is not a benchmark or performance claim. Line 4
now supplies the real unit parser used by `--clock-bound '0.75 s'`. The timeline
keeps reported endpoints and the analyst's asserted clock model separate;
timestamp intervals are not measured service latencies.

## Third gathering: portable replay and decoded evidence

[Replay Review](replay-review/README.md) joins Line 3's evidence packs, Line 2's
raw/decoded JSON review and Line 4's exact time quantities. It verifies a pack
before inspecting all JSON-looking evidence lines, including timeline omissions.
All engine snapshots are unchanged and provenance-bound. Copy the folder to use
it independently with Python 3.10+ and no installed packages.

```sh
python3 -B shared/replay-review/replay_review.py demo
```

Observed: two events, one explicit omission, seven decoded findings and tampering
rejected. Fifteen integration tests pass. Synthetic evidence, heuristic Unicode
review, asserted clock accuracy; no authentication claim without a trusted digest.
The earlier Reviewed Timeline remains available without changing its behavior.
