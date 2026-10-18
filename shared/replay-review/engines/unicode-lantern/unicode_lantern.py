#!/usr/bin/env python3
"""Bounded, offline Unicode triage. Python standard library only."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import unicodedata as ud

VERSION = "1.0.0"
MAX_BYTES = 2 * 1024 * 1024
MAX_FINDINGS = 1000
BIDI = set("\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
# Deliberately small, case-sensitive visual heuristic; NOT the UTS #39 skeleton.
LOOKALIKES = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p",
    "\u0441": "c", "\u0445": "x", "\u0443": "y", "\u0456": "i",
    "\u0458": "j", "\u0455": "s", "\u04bb": "h",
    "\u0410": "A", "\u0412": "B", "\u0415": "E", "\u041a": "K",
    "\u041c": "M", "\u041d": "H", "\u041e": "O", "\u0420": "P",
    "\u0421": "C", "\u0422": "T", "\u0425": "X", "\u0406": "I",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0396": "Z",
    "\u0397": "H", "\u0399": "I", "\u039a": "K", "\u039c": "M",
    "\u039d": "N", "\u039f": "O", "\u03a1": "P", "\u03a4": "T",
    "\u03a5": "Y", "\u03a7": "X", "\u03bf": "o",
})
DEMO = "owner = 1\n\u043ewner = 2\nname\u200b = 3\n# hidden \u202eevil\u202c\n\uff4fwner = 4\n"


def escaped(text):
    """An ASCII representation safe to display even after parsing the JSON."""
    return text.encode("unicode_escape").decode("ascii")


def character_rule(char):
    cp, category = ord(char), ud.category(char)
    if char in BIDI:
        return "bidi-control", "Explicit bidirectional control can change visual reading order."
    if category == "Cf":
        return "format-character", "Format character may be invisible or alter adjacent text."
    if category == "Cc" and char not in "\t\n\r":
        return "control-character", "Control character can affect terminals or text processing."
    if char != " " and category in {"Zs", "Zl", "Zp"}:
        return "unusual-separator", "Separator can resemble a space or create an unexpected line boundary."
    if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
        return "variation-selector", "Variation selector modifies a preceding glyph and may be invisible."
    if cp in {0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x3164, 0xFFA0}:
        return "invisible-character", "Character may have no independently visible glyph."
    return None


def script_family(char):
    # Unicode character names are a heuristic, not the Script property database.
    name = ud.name(char, "")
    for script in ("LATIN", "CYRILLIC", "GREEK"):
        if name.startswith(script + " "):
            return script
    return None


def scan(raw, source="<memory>", max_findings=MAX_FINDINGS):
    if not isinstance(raw, bytes):
        raise ValueError("input must be UTF-8 bytes")
    if len(raw) > MAX_BYTES:
        raise ValueError(f"input exceeds {MAX_BYTES} bytes")
    if type(max_findings) is not int or not 1 <= max_findings <= MAX_FINDINGS:
        raise ValueError(f"max_findings must be between 1 and {MAX_FINDINGS}")
    text = raw.decode("utf-8", errors="strict")
    findings, count, seen = [], 0, {}

    def add(rule, position, value, explanation, **extra):
        nonlocal count
        count += 1
        if len(findings) < max_findings:
            findings.append(dict(rule=rule, **position, escaped=escaped(value),
                                 explanation=explanation, **extra))

    def token_check(token, start):
        if not token:
            return
        families = sorted({s for ch in token if (s := script_family(ch))})
        if len(families) > 1:
            add("mixed-script-identifier", start, token,
                "Identifier mixes Latin, Greek or Cyrillic letter families; review in context.",
                scripts=families)
        normalized = ud.normalize("NFKC", token)
        if normalized != token:
            add("compatibility-normalization", start, token,
                "Identifier changes under NFKC normalization.", normalized=escaped(normalized))
        skeleton = normalized.translate(LOOKALIKES)
        previous = seen.get(skeleton)
        if previous and previous[0] != token:
            add("lookalike-collision", start, token,
                "Distinct identifiers share this tool's limited visual skeleton.",
                skeleton=escaped(skeleton), first=dict(**previous[1], escaped=escaped(previous[0])))
        elif previous is None:
            seen[skeleton] = (token, start)

    line, column, byte_offset = 1, 1, 0
    token_chars, token_start = [], None
    for index, char in enumerate(text):
        position = dict(line=line, column=column, char_offset=index, byte_offset=byte_offset)
        # Python-like identifiers, including combining marks after the first letter.
        continuation = ("a" + char).isidentifier()
        if token_chars and not continuation:
            token_check("".join(token_chars), token_start)
            token_chars = []
        if token_chars:
            token_chars.append(char)
        elif char == "_" or char.isidentifier():
            token_chars, token_start = [char], position
        rule = character_rule(char)
        if rule:
            add(rule[0], position, char, rule[1], codepoint=f"U+{ord(char):04X}",
                unicode_name=ud.name(char, "UNNAMED"))
        byte_offset += len(char.encode("utf-8"))
        if char == "\n":
            line, column = line + 1, 1
        else:
            column += 1
    token_check("".join(token_chars), token_start)
    return dict(schema_version=1, tool="unicode-lantern", tool_version=VERSION,
                unicode_version=ud.unidata_version, source=escaped(source),
                sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), characters=len(text),
                finding_count=count, findings=findings, truncated=count > len(findings),
                assessment="review-required" if count else "no-covered-patterns-found",
                limitations=["Heuristic triage, not proof of deception or absence of deception.",
                             "Not a language parser; identifiers in comments and strings also count.",
                             "Limited Latin/Greek/Cyrillic mapping, not full Unicode confusables.",
                             "Columns count Unicode code points, not screen cells; only LF starts a line."])


def workspace_file(value):
    path = Path(value).resolve()
    root = Path.cwd().resolve()
    if not path.is_relative_to(root):
        raise ValueError("input must resolve inside the current workspace")
    if not path.is_file():
        raise ValueError("input must be a regular file")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="explicit UTF-8 text file inside the current workspace")
    group.add_argument("--demo", action="store_true", help="scan built-in illustrative text, no file access")
    parser.add_argument("--max-findings", type=int, default=MAX_FINDINGS)
    args = parser.parse_args(argv)
    try:
        if args.demo:
            raw, source = DEMO.encode("utf-8"), "<built-in-demo>"
        else:
            path = workspace_file(args.file)
            with path.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            source = str(path.relative_to(Path.cwd().resolve()))
        result = scan(raw, source, args.max_findings)
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    # Demo intentionally succeeds; an actual file with findings exits 1 for CI use.
    return 0 if args.demo or not result["finding_count"] else 1


if __name__ == "__main__":
    sys.exit(main())
