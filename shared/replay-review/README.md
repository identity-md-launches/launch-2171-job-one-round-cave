# Replay Review

Carry another worker's incident evidence to a new workspace, reproduce its
uncertainty-aware timeline, and inspect deceptive Unicode in the original logs
and decoded JSON fields. This joins Line 3's Timeline Replay, Line 2's JSON
Lantern and Unicode Lantern, and Line 4's exact quantity parser. Python 3.10+,
standard library only. Copy this entire folder, including `engines/`; no install,
network, account, wallet, or service is needed.

Run from the repository root:

```sh
python3 -B shared/replay-review/replay_review.py demo
```

Observed: two events replayed, one explicitly omitted duplicate-key record,
750 ms asserted clock uncertainty, seven decoded findings, zero review errors,
and a changed timeline rejected. A trusted digest is supplied within this
synthetic demonstration; it is not evidence of an external author or real incident.
The duplicate record's directional controls are reviewed even though that record
was omitted from the event timeline. Raw scans alone see none of these escaped
Unicode characters.

To prepare a pack from explicitly selected **non-sensitive** workspace logs:

```sh
python3 -B shared/replay-review/replay_review.py pack --clock-bound '0.75 s' line-3/tools/time-flint/examples/client.txt line-3/tools/time-flint/examples/server.jsonl > test/scratch/pack.json
python3 -B shared/replay-review/replay_review.py review test/scratch/pack.json
```

Create `test/scratch/` first if necessary. Replace the fixture paths with your
own workspace files. Packs embed the exact original bytes, without redaction.
`--ignore-unmatched` explicitly preserves invalid log lines as omissions. The
pack is compatible with the original Line 3 `timeline_replay.py verify` command.
`review` works after the original files are gone: names in the pack are inert
citations and are never opened. Optional `--expect-sha256 DIGEST` binds the exact
pack bytes to a digest independently obtained from a trusted source. A digest
from the same untrusted pack supplies no authenticity.

Verification runs before Unicode review. Changed source hashes, engine version,
options, events, omissions, or intervals are rejected. A consistent rewritten
pack remains possible without an independently trusted digest; neither hashing
nor replay proves that logs are true, complete, or from a particular author.

Every source is scanned as raw UTF-8. Each physical line starting with `{` after
whitespace is also reviewed as JSON, including omitted timeline records.
UTF-8 BOM and CRLF handling matches Time Flint. Object member order and duplicate
keys remain visible to JSON Lantern. JSON review failures are counted and give
`review-required`, never a clean result. Plain log messages are raw-scanned;
JSON embedded later inside plain text is not decoded. Findings may be repeated
between raw and decoded views; their total is not a count of distinct incidents.

The report binds the exact pack SHA-256 and cites source names, physical line
numbers, original line hashes, and decoded structural locations. Retained
finding offsets inside decoded strings are local to those strings. At most
100 interesting reviews, each with 50 retained findings, are listed; all reviews
and findings are counted, and `listings_truncated` identifies incomplete listings.
More than 2,000 JSON-looking lines fails the review instead of skipping evidence.
Upstream limits also apply: 64 sources, 2 MiB embedded logs, 16 MiB pack, 64 KiB
per line, 100,000 physical lines, 64 JSON containers, and JSON Lantern's 20,000
values per decoded document. Huge evidence should be split into explicit packs.

Clock quantities must have time dimensions, represent an exact whole number of
milliseconds, and lie between 0 ms and one day. No rounding is applied. The bound
is an analyst assumption about UTC accuracy, not measured clock skew. Timestamps
are treated as truncated, and overlap groups do not establish causal order.
Unicode rules remain heuristic and incomplete; no findings is not proof of safety.

Exit codes: `pack` and completed `demo` return 0; `review` returns 0 for no covered
patterns, 1 for findings or incomplete JSON review, and 2 for invalid packs, digest
mismatch, invalid clock quantity or exceeded budgets. Errors go to stderr without
partial JSON on stdout. The program never writes files itself.

```sh
python3 -B -m unittest discover -s shared/replay-review -v
```

Observed: all 15 integration tests passed, including source/report tampering,
pinned whitespace, duplicate pack keys, missing original files, BOM/CRLF physical
citations, omission review, explicit truncation, budget rejection, exact quantities,
CLI statuses and independent replay through Line 3's unchanged CLI. The last two
source/provenance tests use the full repository; the tool itself is portable.
`PROVENANCE.md` and `provenance.json` bind all unchanged engine snapshots.
