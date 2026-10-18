# Line 3 — incident timelines

The first piece, [Time Flint](tools/time-flint/README.md), merges plain UTF-8 logs
and JSONL into a reproducible UTC timeline. It preserves source citations and
marks timestamp intervals whose order cannot be established from their stated
precision. `GOAL.md` is the line's one thing.

## Mark 01: Pebbles in Time

Pepe arranges scattered pebbles into a trail on the illuminated cave wall. The
frog and trail were added to the supplied bare cave for this first round. The
wall's square framing, roots, cracks, rough rock, and torchlit color remain.

Output inspection: `artifacts/line-3/wall.png` is a 1254 × 1254 PNG at the supplied
cave's dimensions; `dist/line-3/01.jpg` is a 512 × 512 JPEG preview. The JSON
record contains the finished PNG's SHA-256. Visual review found a wide mouth,
heavy-lidded eyes, worn ochre and charcoal pigments, and no text or symbols.
The hands are concealed and no handprints appear, so there are no visible digits
to miscount. Unmet visual requirements observed: none.

## Mark 22: Bounded Time

Time Flint now handles calendar extremes as validation errors, bounds workspace
input reads, and lets an analyst assert a symmetric clock uncertainty bound.
Original timestamp evidence remains visible beside broadened intervals. See
[the tool README](tools/time-flint/README.md) for a working one-command example,
the precise assumptions and the regression suite.

Two ochre pebbles enclosed by overlapping chalk arcs, with charcoal pebbles at
the outer edges, mark the difference between an observed timestamp and an
uncertain interval. No earlier record was changed. The new number is 22 because
21 numbered records, including reserved slots, already existed.

The built-in image tool edited the existing wall with this prompt:

> Keep the square cave, its rock, roots, cracks, torchlight, existing Pepe and
> pebble trail. Add only two small ochre pebbles in the blank upper-right rock,
> each enclosed by an uneven overlapping chalk arc, with charcoal pebbles at
> the outer ends. Use worn earth pigments. No new hands, text, digits, logos,
> signatures, borders, photographs or 3D rendering.

The complete generation prompt is retained in [wall-review.json](wall-review.json).
For preservation, only the new mark's empty-rock patch was composited into the
original. Every original pixel outside x=710..1044, y=355..554 is unchanged,
including the whole earlier Pepe and pebble trail. This was checked against the
original PNG's decoded pixels. A 12-pixel join lies inside that rectangle.

The finished `artifacts/line-3/wall.png` and required named output
`artifacts/line-3/wall-v2.png` contain identical 1254 × 1254 RGB8 PNG bytes.
`dist/line-3/22.jpg` is a 512 × 512 baseline JPEG under 100 KB.
`dist/line-3/22.json` references the finished PNG's SHA-256.

Visual review of the final PNG: the earlier Pepe's wide mouth and heavy-lidded
eyes remain intact; the new arcs use chalk, charcoal, red and yellow ochre.
No letters, numbers, captions, logos, watermarks, borders or frames were seen.
No hands or handprints were added; the earlier hands remain concealed, so there
are no visible hand digits to count. The square size, cave framing and light
are preserved. Unmet visual requirements observed: none. This inspection does
not claim automatic visual certification. Raster formats, checks, prompt and
file properties are recorded in `wall-review.json`.

## Mark 23: Retraced Time

[Timeline Replay](tools/timeline-replay/README.md) gives a worker a portable JSON
pack of exact log bytes, parser identity, assumptions and the resulting timeline.
It replays without the original files and rejects inconsistent evidence or reports.
An optional independently trusted pack digest binds all file bytes. A matching
replay alone establishes consistency, not authentic or complete logs.

Try it from the repository root:

```sh
python3 -B line-3/tools/timeline-replay/timeline_replay.py demo
```

Observed: two synthetic events and one omission replayed successfully at an
asserted ±750 ms clock bound, and an altered message was rejected. Twenty new
tests and the original 28 Time Flint tests passed. CLI checks also replayed a
pack after deleting the scratch source copies. Results are recorded in
`cli-check-23.json` and `round-23-review.json`.

The new mark is two short matching pebble trails between the older chalk arcs
and the original trail. The image tool supplied the pigments; only the empty-rock
patch x=735..909, y=580..694 was composited into the inherited wall. Every pixel
outside that patch, including every earlier painted mark and the entire Pepe,
is unchanged. `image-check-23.json` records the decoded-pixel comparison.

`artifacts/line-3/wall-v3.png` is the required 1254 × 1254 RGB8 PNG;
`artifacts/line-3/wall.png` aliases it. `dist/line-3/23.jpg` is a 512 × 512 JPEG
of 66,664 bytes. `dist/line-3/23.json` references the PNG's SHA-256.
Visual inspection of both final images found no text or numbers and no unmet
visual requirements. No hands or handprints were added, and the ancestral
hands remain concealed, so there are no visible hand digits to count. Rock,
roots, cracks, lighting and framing remain unchanged outside the small patch.
