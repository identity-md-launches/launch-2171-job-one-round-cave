# Timeline Replay

Give another analyst the exact evidence needed to reproduce an incident timeline,
even after the original log files are unavailable. A JSON pack includes the original
log bytes (base64), source names and SHA-256 hashes, explicit omission/clock options,
the shipped parser's source hash, and the complete Time Flint report. Verification
recomputes the report from the embedded bytes; it never opens paths named by a pack
or executes code supplied by one. Python 3.10+, standard library only; copy this
whole folder, including `vendor/`, to use it independently.

One command from the repository root shows it working, without creating files:

```sh
python3 -B line-3/tools/timeline-replay/timeline_replay.py demo
```

Observed locally: `verified: true`, two sources, two events, one explicit omission,
a 750 ms asserted clock bound, and `tampered_report_rejected: true`. The inputs are
**synthetic**, including a UTF-8 BOM, CRLF line endings and an untimestamped line.
This is a reproducibility demonstration, not a real incident or measured clock skew.

To pack the existing line's two synthetic fixtures and verify the result:

```sh
python3 -B line-3/tools/timeline-replay/timeline_replay.py pack --clock-uncertainty-ms 750 line-3/tools/time-flint/examples/client.txt line-3/tools/time-flint/examples/server.jsonl > test/scratch/timeline-pack.json
python3 -B line-3/tools/timeline-replay/timeline_replay.py verify test/scratch/timeline-pack.json
```

Create `test/scratch/` first if needed, or choose another output file in your own
workspace. `pack` emits only the pack on stdout. `verify` emits a compact result
and SHA-256 of the **exact pack file bytes**, including whitespace. To bind review
to an independently retained digest, use `verify PACK --expect-sha256 DIGEST`,
where DIGEST is that actual 64-character lowercase SHA-256. Errors return exit 2
with escaped diagnostics. Successful commands return 0. No file is written by the
program itself. Use `--ignore-unmatched` only when you want malformed lines
explicitly represented in the report's `omitted` list.

## What verification establishes

The recorded engine hash must match the shipped `vendor/time_flint.py`. Every
embedded source must match its hash. The entire report must then match an exact
replay, including source/line citations, original hashes, messages, precision,
half-open UTC endpoints, overlap groups, clock assumptions and omissions. JSON
comparison distinguishes booleans from integers. Unknown fields, duplicate keys,
nonstandard numbers, invalid UTF-8, noncanonical base64 and excessive nesting fail.
Source names remain inert citation strings, even when no such file exists.

An unpinned pack proves internal consistency only. Someone able to change both
logs and the resulting report can create another consistent pack. The optional
**independently trusted** digest detects replacement of any pack bytes; a hash
copied from the same untrusted pack or verification output supplies no authenticity.
Neither mode establishes that logs were truthful, complete or collected by a
particular person. A local engine-file hash detects version mismatch, not a
compromised runtime. Packs include the full original logs, without redaction.

Clock bounds retain Time Flint's meaning: ±N ms is an analyst assertion, not a
measurement. Timestamps are assumed truncated to their displayed precision.
Overlap groups connect intervals transitively and do not imply causal order.
No clocks, services, networks, accounts, wallets, coins or transactions are used.

## Limits and checks

Explicit source/pack files must be regular files resolving inside the current
working directory. No directory traversal, stdin or automatic discovery is used.
This path check is not a filesystem sandbox against concurrent changes. Embedded
sources are limited to 64 and 2 MiB total; packs to 16 MiB; Time Flint's 100,000
physical-line, 64 KiB-line, JSON-depth and UTC-calendar limits also apply. Reads
are capped at the remaining byte limit plus one. A report exceeding the pack limit
fails rather than truncating evidence. The format is uncompressed and bounded,
but has no streaming mode. Calendar overflow remains fatal for a clock model.

```sh
python3 -B -m unittest discover -s line-3/tools/timeline-replay -v
```

Observed: **20 tests passed**, covering exact BOM/CRLF byte retention, deterministic
packs, independent replay, altered source/report/options, removed events/omissions,
engine mismatches, pinned file hashes, malformed JSON/base64, byte limits and path
boundaries. The original Time Flint suite also passed all 28 tests. A separate CLI
exercise packed logs, deleted the original copies and successfully verified the
pack, then rejected a changed message and an incorrect externally pinned digest.

See [PROVENANCE.md](PROVENANCE.md) for the parser snapshot and its source hash.
