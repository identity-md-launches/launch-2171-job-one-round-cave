# JSON Lantern

Review Unicode hidden behind JSON escapes, including decoded member names and
string values. Preserve duplicate members instead of silently accepting the
last value. Report exact duplicate keys and keys sharing Unicode Lantern's
limited NFKC/look-alike skeleton within the same object. Input is never changed.

From the repository root, with Python 3.9+ and no packages or network:

```sh
python3 -B line-2/tools/json-lantern/json_lantern.py --demo
```

The demo returns six findings and exit 0. The same bytes produce **zero**
findings in the ancestral raw-text scanner: every suspicious character is
encoded as a JSON escape. Decoding exposes a Cyrillic look-alike, a key
collision, a duplicate `owner` key, two directional controls, and a zero-width
space. This example illustrates behavior; it is not a real attack observation.

Review an explicitly chosen, non-sensitive JSON file inside this workspace:

```sh
python3 -B line-2/tools/json-lantern/json_lantern.py --file dist/line-2/22.json
```

File mode exits **0** for no covered patterns, **1** for findings, **2** for
invalid input or exceeded limits. Demo mode deliberately returns 0 on completion.
JSON evidence goes to stdout; argument usage errors go to stderr. No directory
scan, HTTP request, wallet, signing, posting, environment access or auto-repair.

## Reading evidence

The original-byte SHA-256 binds the complete input. Findings have domains:

- `decoded-string`: Unicode Lantern evidence on one decoded key or value,
  with that string's UTF-8 SHA-256. Its byte and character offsets, line and
  column refer **only to that string**, never to JSON source-token offsets.
- `object-key`: duplicate or limited-skeleton collision with a citation to
  the first matching member in the same object. Whole keys are compared,
  including punctuation; no key/value is discarded.
- `raw-json`: ancestral scanner findings in the original bytes, with original
  source offsets. These may overlap conceptually with decoded findings.

Structural `location` lists start at the root (`[]`). Array segments are
`{"index": 0}`. Object segments are `{"pair": 0, "role": "key"}` or
`{"pair": 0, "role": "value"}`. All indexes are zero-based. Pair indexes
refer to source member order, making even duplicate names unambiguous. A key
containing slashes, tildes or hidden characters never becomes path syntax.
Decoded findings use the original scanner's one-based code-point line/column,
zero-based byte/character offsets and LF-only line accounting.

Evidence and source names use ASCII escape notation, safe even after JSON
decoding. Do not reinterpret those escape sequences as terminal commands.
Each report records Python's Unicode database version and the scanner version.

## Limits

Input is strict UTF-8 JSON, at most 2 MiB, 64 nested containers and 20,000
values (root included; member names do not count as values). A UTF-8 BOM,
JSONL, NaN/Infinity and lone surrogate escapes are rejected. Valid surrogate
pairs are decoded normally. Numbers are validated by the JSON grammar but
are opaque to Unicode review, avoiding floating-point rounding or overflow.

At most 1,000 findings are retained globally; `--max-findings 20` lowers this.
Scanning continues to count omitted findings and `truncated` signals omission.
Malformed or over-budget input is an error, never a partial clean assessment.
Output is deterministic: object keys first, child values in source order,
then raw-source findings. This is not overall source-byte sorting.

The sibling `../unicode-lantern/unicode_lantern.py` is a required, unchanged,
standard-library dependency; copy both tool folders when moving this tool.
No configuration or installed dependency is needed. Paths resolving outside
the current working directory are rejected before opening. As with the
ancestral scanner, use a stable workspace: path validation cannot prevent a
concurrent process from swapping a file after validation.

The mapping remains a small case-sensitive heuristic, **not UTS #39** or a
complete confusables table. Identifier comparisons are local to each string;
key collisions are local to each object. There is no cross-value identifier
comparison, rendered-document analysis or language parsing. Raw/decoded
findings can count the same character twice. Legitimate multilingual strings
can trigger findings; no findings does not establish safety.

## What happened when tried

On Python 3.12.3 / Unicode 15.0.0, all 17 new tests passed. They cover the
raw/decoded gap, duplicate preservation, structural paths, decoded byte offsets
after astral text and CRLF, whole-key collisions, global truncation, malformed
JSON/UTF-8, surrogates, strict numbers, and depth/size/value budgets. The 12
ancestral Unicode Lantern tests also passed unchanged. A read-only review of
the real existing `dist/line-2/01.json` returned zero covered patterns; that is
an observation about these rules, not an endorsement of the document.

```sh
python3 -B -m unittest discover -s line-2/tools/json-lantern -v
```

The mark for this piece is a closed shell beside an opened shell revealing
a pale pebble: decoded contents made reviewable.
