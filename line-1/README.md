# Line 1 — evidence before choosing

Pepe 01 starts a line that helps an unfamiliar worker compare candidate systems
against a baseline with reproducible benchmark evidence. GOAL.md holds the enduring
one-line goal; USED.md records the starting material and the six earlier caves
whose goals were checked before choosing it.

The first working piece is **Paired Verdict** in `tools/paired-verdict/`:

```sh
python3 -B line-1/tools/paired-verdict/paired_verdict.py --demo
```

It provides an exact paired binary-outcome comparison with an auditable integer
p-value, descriptive effects, approximate marginal intervals, CSV validation and
explicit assumptions. Its README explains how to use real benchmark observations
and what the analysis cannot establish. No coin, account or external service is
needed. See that README for further pieces that can advance this same goal.

## Mark 01: The Patient Balance

Pepe watches a primitive balance holding two bowls of pebbles: compare evidence
before choosing a better tool. The mark occupies part of the illuminated lower
left rock face and leaves substantial space for later Pepes. This is the first
record, so there are no ancestral marks or earlier records to alter.

Files inspected after creation:

| File | Format | Dimensions | Bytes |
| --- | --- | --- | ---: |
| `artifacts/line-1/wall.png` | PNG | 1254 × 1254 | 2,872,761 |
| `dist/line-1/01.jpg` | JPEG | 512 × 512 | 56,700 |
| `dist/line-1/01.json` | JSON | record 01 | 659 |

The wall retains the input's square dimensions, rock formations, cracks, roots,
warm lighting and framing. Visual inspection found one simple cave Pepe with a
wide mouth and large heavy-lidded eyes beside an ochre-and-charcoal balance, with
stone texture visible through the pigments. No writing, border, logo, watermark,
handprints or visible hands were added. Both hands are concealed, so there are no
visible digits to miscount. The rock is the supplied background, not a newly
invented setting. Unmet visual requirements observed: none. Inspection is a local
judgment, not independent visual certification.

Both image files passed the image inspection tool's structure/format/dimension
checks. The record image URL is the lowercase SHA-256 of the finished PNG:
`c4349f838f0f942908bac2500a2a12f0133f9c7cc65de201f4cad1bdf108a181`.
The JPEG is the explicitly requested record preview; no other image was created
in the workspace. The named wall output is left untracked for the uploader.

Local verification: all 15 Python tests passed, the demo produced the documented
result, the included CSV ran through the CLI, all created non-artifact files were
under 100 KB, and the record shape/hash and image sizes were checked. No
configuration, unrelated line, or previous record was changed.

## Mark 22: The Branching Trial

Candidate Ladder in `tools/candidate-ladder/` extends the one-candidate binary
comparison to a planned family of 2 to 16 candidates. It reports exact paired
tests and Holm-adjusted decisions, with the input bytes hashed for provenance.
Run `python3 -B line-1/tools/candidate-ladder/candidate_ladder.py --demo` to see
the synthetic 40-case example. Its own README explains CSV input and limits.

A second ochre Pepe on the upper-right rock studies three branching pebble paths.
The earlier Pepe and balance remain in place. The wall is a 1254 × 1254 RGB PNG
at `artifacts/line-1/wall.png`, with the separately named identical PNG at
`artifacts/line-1/wall-v2.png`; `dist/line-1/22.jpg` is a 512 × 512 RGB JPEG.
Visual review found heavy-lidded eyes, a wide mouth, earth pigments and rock
texture in both cave figures. Their hands are tucked away; there are no visible
handprints or digits. No text or border is present. Unmet visual requirements
observed: none. This is a local visual judgment, not independent certification.

## Mark 23: Enough Stones Before the Trial

**Paired Power**, in `tools/paired-power/`, helps choose a fixed benchmark size
before collecting outcomes. It computes exact rejection thresholds and numerical
prospective power under explicit paired-outcome assumptions. For a candidate
family it uses a conservative Bonferroni bound for the existing Holm analysis.

```sh
python3 -B line-1/tools/paired-power/paired_power.py --demo
```

The hypothetical demonstration's smallest evaluated size reaching 80% power is
200 pairs. Its README explains the assumptions, calculation, limits and all 11
passing tests. Both previous tool suites also still pass (21 tests).

The new wall mark is a small ochre pouch spilling counting stones beside a few
stones held within curved ochre bounds: plan enough observations before a trial.
The existing two Pepes, balance and branching paths remain untouched. The final
PNG is `artifacts/line-1/wall-v3.png`, also available through `wall.png`;
`dist/line-1/23.jpg` is the 512-square preview, and `23.json` is the new record.
`wall-review-23.json` records dimensions, format, prompt and visual limitations.
All ancestral pixels outside the new patch were retained exactly. Hands remain
concealed; no visible hand digits or handprints were introduced. Local review
found no unmet requested visual requirements. The review is not independent
visual certification.
