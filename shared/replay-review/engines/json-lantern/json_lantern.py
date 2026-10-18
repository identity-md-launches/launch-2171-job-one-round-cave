#!/usr/bin/env python3
"""Bounded JSON Unicode evidence, without executing or rewriting input."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unicodedata


# Reuse the ancestral scanner, including its documented heuristic limitations.
SCANNER = Path(__file__).resolve().parents[1] / "unicode-lantern" / "unicode_lantern.py"
spec = importlib.util.spec_from_file_location("json_lantern_scanner", SCANNER)
lantern = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lantern)
MAX_BYTES = lantern.MAX_BYTES
MAX_DEPTH = 64
MAX_NODES = 20000
DEMO = br'{"owner":1,"\u043ewner":2,"owner":3,"message":"hidden \u202eevil\u202c","nested":{"a/b~":["name\u200b"]}}'


class Pairs(list):
    """Distinguish JSON objects from arrays and retain repeated member names."""


def check_depth(text):
    """Bound containers before the recursive stdlib JSON decoder is entered."""
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError(f"JSON nesting exceeds {MAX_DEPTH}")
        elif char in "]}":
            depth -= 1


def reject_constant(value):
    raise ValueError("non-finite JSON number is not allowed")


def review(raw, source="<memory>", max_findings=1000):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError(f"input must be UTF-8 bytes, at most {MAX_BYTES} bytes")
    if type(max_findings) is not int or not 1 <= max_findings <= 1000:
        raise ValueError("max_findings must be between 1 and 1000")
    text = raw.decode("utf-8", errors="strict")
    check_depth(text)
    # Numbers are opaque to text review. Keep their lexical spelling to avoid
    # int-conversion limits, float overflow, or loss of precision. They are never
    # treated as strings by traversal (the marker is a separate type).
    class Number:
        def __init__(self, spelling):
            pass
    tree = json.loads(text, object_pairs_hook=Pairs, parse_int=Number,
                      parse_float=Number, parse_constant=reject_constant)
    findings, total, strings, nodes = [], 0, 0, 0

    def emit(item):
        nonlocal total
        total += 1
        if len(findings) < max_findings:
            findings.append(item)

    def scan_string(value, location):
        nonlocal strings, total
        strings += 1
        # JSON permits unpaired surrogate escapes; they have no valid UTF-8
        # encoding. Refuse them explicitly rather than inventing byte offsets.
        encoded = value.encode("utf-8", errors="strict")
        report = lantern.scan(encoded, max_findings=max_findings)
        for finding in report["findings"]:
            emit(dict(domain="decoded-string", location=location,
                      decoded_sha256=report["sha256"], evidence=finding))
        # All findings still count when a per-string report is truncated.
        total += report["finding_count"] - len(report["findings"])

    # A location is a sequence of array indexes or object-pair indexes. The
    # final object segment distinguishes key from value, even for duplicate keys.
    pending = [(tree, [])]
    while pending:
        value, location = pending.pop()
        nodes += 1
        if nodes > MAX_NODES:
            raise ValueError(f"JSON value count exceeds {MAX_NODES}")
        if isinstance(value, Pairs):
            seen, skeletons = {}, {}
            children = []
            for index, (key, child) in enumerate(value):
                key_location = location + [{"pair": index, "role": "key"}]
                scan_string(key, key_location)
                if key in seen:
                    emit(dict(domain="object-key", rule="duplicate-key",
                              location=key_location, escaped=lantern.escaped(key),
                              first_location=seen[key],
                              explanation="Repeated decoded key; consumers may discard an earlier value."))
                else:
                    seen[key] = key_location
                skeleton = unicodedata.normalize("NFKC", key).translate(lantern.LOOKALIKES)
                previous = skeletons.get(skeleton)
                if previous is not None and previous[0] != key:
                    emit(dict(domain="object-key", rule="lookalike-key-collision",
                              location=key_location, escaped=lantern.escaped(key),
                              skeleton=lantern.escaped(skeleton),
                              first_location=previous[1], first_escaped=lantern.escaped(previous[0]),
                              explanation="Distinct keys in this object share the limited visual skeleton."))
                elif previous is None:
                    skeletons[skeleton] = (key, key_location)
                children.append((child, location + [{"pair": index, "role": "value"}]))
            pending.extend(reversed(children))
        elif isinstance(value, list):
            pending.extend((child, location + [{"index": index}])
                           for index, child in reversed(list(enumerate(value))))
        elif isinstance(value, str):
            scan_string(value, location)

    raw_report = lantern.scan(raw, source, max_findings)
    for finding in raw_report["findings"]:
        emit(dict(domain="raw-json", evidence=finding))
    total += raw_report["finding_count"] - len(raw_report["findings"])
    return dict(schema_version=1, tool="json-lantern", tool_version="1.0.0",
                scanner_version=lantern.VERSION, unicode_version=unicodedata.unidata_version,
                source=lantern.escaped(source), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), values=nodes, decoded_strings=strings,
                finding_count=total, findings=findings, truncated=total > len(findings),
                assessment="review-required" if total else "no-covered-patterns-found",
                location_contract="Object pair and array indexes are zero-based. Decoded evidence offsets refer only to that decoded string; raw-json offsets refer to original bytes.",
                limitations=["Heuristic triage, not a safety verdict or full Unicode confusables coverage.",
                             "Identifier comparisons are local to each string; key comparisons are local to each object.",
                             "Raw and decoded findings can describe the same character and are counted separately.",
                             "Decoded locations are structural paths, not source-token byte offsets.",
                             "Only strict UTF-8 JSON with paired surrogate escapes is accepted; no JSONL or BOM."])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true")
    group.add_argument("--file", help="explicit JSON file inside the current workspace")
    parser.add_argument("--max-findings", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        if args.demo:
            raw, source = DEMO, "<built-in-demo>"
        else:
            path = lantern.workspace_file(args.file)
            with path.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            source = str(path.relative_to(Path.cwd().resolve()))
        result = review(raw, source, args.max_findings)
    except (OSError, ValueError, RecursionError) as error:
        print(json.dumps({"error": lantern.escaped(str(error))}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if args.demo or not result["finding_count"] else 1


if __name__ == "__main__":
    sys.exit(main())
