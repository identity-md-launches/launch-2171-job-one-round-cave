# Engine provenance

`vendor/time_flint.py` is an unmodified snapshot of the ancestral
`line-3/tools/time-flint/time_flint.py` as received for round 23.
SHA-256 of both files: `caa513722a9767e908dc4a5e49711e623e0a34c8b18753c3d01cda8167988e38`.

The source's 28-test regression suite passes. Timeline Replay adds its own
20-test evidence-pack suite and pins this exact engine source hash in each pack.
No package download or runtime dependency is required. No ancestral source was
changed; the copy keeps old packs replayable if Time Flint later evolves.
The parser's original limitations and clock assumptions still apply.
