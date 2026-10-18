# The Evidence Bundle

The third gathering checks every current line tool and adds
[Replay Review](../shared/replay-review/README.md): portable incident replay with
raw and decoded JSON Unicode evidence, including explicitly omitted log records.
It joins unmodified pieces from Lines 2, 3 and 4; all line files remain unchanged.

```sh
python3 -B shared/replay-review/replay_review.py demo
```

Observed synthetic result: two replayed events, one explicit omission, seven
decoded findings, and tampering rejected. Runs offline with Python 3.10+ and
only the standard library. The shared folder is portable with its engine snapshots.
Replay proves consistency; a separately trusted digest can bind exact pack bytes.
It does not prove truthful logs, identity, clock accuracy or safety.

[REPORT.md](REPORT.md) records what was tried for each line, what works, limits,
possible breakage and a bounded direction for 21 Pepes. [COINS.md](COINS.md) says
none: these capabilities do not require a new currency or a contract deployment.

## Reproduce

Read tool sources first, then run from the repository root:

```sh
python3 -B gathering/check_tools.py > gathering/check-results.json
python3 -B gathering/try_tools.py > gathering/demo-results.json
python3 -B gathering/make_preview.py artifacts/gathering/wall-v3.png dist/gathering/03.jpg
python3 -B gathering/build_dist.py
python3 -B gathering/verify.py
```

Observed: **169 passing tests** (122 line, 35 shared, 12 gathering), eight real
source scans and **16 passing CLI exercises**, including expected mismatch and
invalid-input statuses. Time Flint's exact source/test bytes are copied to
`test/scratch/` before its suite runs, so temporary fixtures do not touch the
line folders. `check-results.json` hashes all 57 line files before and after.
The structural checker separately compares 163 tracked ancestral files against
the inherited tree. No package was installed.

## Media

| Path | Format | Dimensions | Bytes |
| --- | --- | --- | --- |
| `artifacts/gathering/wall-v3.png` | RGB8 PNG | 1254 × 1254 | 2,815,196 |
| `artifacts/gathering/wall.png` | relative alias to `wall-v3.png` | same wall | 11-byte link |
| `dist/gathering/03.jpg` | baseline JPEG | 512 × 512 | 96,809 |

PNG SHA-256:
`1dfc13ced7ee35bdbaae5439246fd231f19d62be8818ee18109a3b8d0735760e`.
The declared PNG is an untracked regular file for the separate artifact uploader.
The alias prevents a second PNG copy in the source bundle. Prior gathering
records, previews and the prior full PNG remain intact.

The image tool edited Gathering 02, adding a small charcoal loop with three
chalk dabs and a red ochre closure beside Pepe's head. Seated Pepe, all previous
marks, rock, cracks, roots, warm light and framing visually remain in place.
Full PNG and decoded JPEG were inspected. Both visible hands have five digits,
four fingers and one thumb each; no extra hands or stencils. No letters,
numbers, signatures, logos, frames or prohibited symbols were observed.
**Unmet visual requirements: none observed.** Generative editing does not
promise pixel-identical unpainted regions. `wall-review.json` records the visual
review; `validation.json` records independent structural checks, not visual
certification. No intermediate image or extra preview was saved in the workspace.

`dist/gathering/03.json` and `dist/one.json` reference the actual whole-wall hash.
The self-contained gallery HTML uses local JPEG previews, inline styling and no
script/font/style dependency. Full-resolution artifact links require network.
All 112 numbered records are shown by wall, painted newest first; 98 placeholders
are retained. The four original goals are reproduced verbatim in `dist/goals.json`.
This is a later gathering, so no first-gathering placeholder regeneration was needed.

`gallery-check.json` records Chromium layout checks at 320, 390 and 1440 px:
112 cards, no horizontal overflow, no broken loaded image and no page error.
All 15 image references were additionally checked to resolve to local JPEGs.
`portable-check.json` records the new shared demo running from a copied folder
without any line directories. No browser screenshot or extra image was saved.
