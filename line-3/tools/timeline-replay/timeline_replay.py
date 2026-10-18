#!/usr/bin/env python3
"""Pack exact log bytes and replay a timeline offline, without reopening log paths."""
import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

# Fixed, shipped source only. A pack can never choose executable code.
from vendor import time_flint as engine

MAX_PACK_BYTES = 16 * 1024 * 1024
MAX_RAW_BYTES = 2 * 1024 * 1024
FORMAT = "timeline-replay/1"
ENGINE = Path(__file__).resolve().parent / "vendor" / "time_flint.py"


class ReplayError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def exact_keys(obj, keys, label):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ReplayError(f"{label}: unexpected or missing fields")


def options_check(options):
    exact_keys(options, ("ignore_unmatched", "clock_uncertainty_ms"), "options")
    if type(options["ignore_unmatched"]) is not bool:
        raise ReplayError("ignore_unmatched must be a boolean")
    bound = options["clock_uncertainty_ms"]
    if type(bound) is not int or not 0 <= bound <= 86400000:
        raise ReplayError("clock_uncertainty_ms must be an integer in 0..86400000")


def make_pack(inputs, ignore_unmatched=False, clock_uncertainty_ms=0):
    options = dict(ignore_unmatched=ignore_unmatched, clock_uncertainty_ms=clock_uncertainty_ms)
    options_check(options)
    if not 1 <= len(inputs) <= engine.MAX_SOURCES:
        raise ReplayError("supply 1..64 log sources")
    if any(not isinstance(name, str) or not isinstance(data, bytes) for name, data in inputs):
        raise ReplayError("source names must be text and contents bytes")
    if sum(len(data) for _, data in inputs) > MAX_RAW_BYTES:
        raise ReplayError("embedded logs exceed 2 MiB total")
    timeline = engine.build(inputs, **options)
    pack = {
        "format": FORMAT,
        "engine_sha256": digest(ENGINE.read_bytes()),
        "options": options,
        "inputs": [{"source": name, "sha256": digest(data),
                    "base64": base64.b64encode(data).decode("ascii")} for name, data in inputs],
        "timeline": timeline,
    }
    if len(canonical(pack)) + 1 > MAX_PACK_BYTES:
        raise ReplayError("serialized pack exceeds 16 MiB")
    return pack


def verify_pack(pack):
    exact_keys(pack, ("format", "engine_sha256", "options", "inputs", "timeline"), "pack")
    if pack["format"] != FORMAT:
        raise ReplayError("unsupported pack format")
    if pack["engine_sha256"] != digest(ENGINE.read_bytes()):
        raise ReplayError("engine source hash does not match shipped parser")
    options_check(pack["options"])
    sources = pack["inputs"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= engine.MAX_SOURCES:
        raise ReplayError("inputs must contain 1..64 sources")
    inputs, total = [], 0
    for source in sources:
        exact_keys(source, ("source", "sha256", "base64"), "input")
        if not all(isinstance(source[key], str) for key in source):
            raise ReplayError("input fields must be strings")
        encoded = source["base64"]
        if len(encoded) > 4 * ((MAX_RAW_BYTES - total + 2) // 3):
            raise ReplayError("embedded logs exceed 2 MiB total")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ReplayError("invalid base64 source") from exc
        total += len(data)
        if total > MAX_RAW_BYTES:
            raise ReplayError("embedded logs exceed 2 MiB total")
        if base64.b64encode(data).decode("ascii") != encoded:
            raise ReplayError("noncanonical base64 source")
        if digest(data) != source["sha256"]:
            raise ReplayError("embedded source hash mismatch")
        # Source names are inert citations, never filesystem paths during replay.
        inputs.append((source["source"], data))
    result = engine.build(inputs, **pack["options"])
    # Serialized comparison distinguishes True from 1, unlike Python equality.
    if canonical(result) != canonical(pack["timeline"]):
        raise ReplayError("timeline differs from exact replay of embedded evidence and options")
    return {"verified": True, "sources": len(inputs), "events": len(result["events"]),
            "omitted": len(result["omitted"]), "clock_uncertainty_ms": pack["options"]["clock_uncertainty_ms"]}


def read_workspace(name, limit):
    root = Path.cwd().resolve()
    path = Path(name).resolve()
    if not path.is_relative_to(root):
        raise ReplayError("input resolves outside the current workspace")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ReplayError("input must be a regular workspace file")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ReplayError("input exceeds byte limit")
    return data


def load_pack(raw):
    if len(raw) > MAX_PACK_BYTES:
        raise ReplayError("pack exceeds 16 MiB")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=engine.unique_object,
                           parse_constant=engine.reject_constant)
        engine.check_json_depth(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ReplayError("invalid pack JSON: " + str(exc)) from exc


def demo():
    # Explicitly synthetic evidence: includes exact BOM/CRLF and an omission.
    inputs = [("client.log", b"\xef\xbb\xbf2026-10-18T10:00:00Z accepted\r\nuntimestamped diagnostic\r\n"),
              ("server.jsonl", b'{"ts":1792317602000,"message":"completed"}\n')]
    pack = make_pack(inputs, True, 750)
    raw = canonical(pack) + b"\n"
    result = verify_pack(load_pack(raw))
    changed = load_pack(raw)
    changed["timeline"]["events"][0]["message"] = "altered conclusion"
    try:
        verify_pack(changed)
    except ReplayError:
        rejected = True
    else:
        raise ReplayError("demo failed to reject an altered timeline")
    return {"example": "synthetic, not a real incident", "replay": result,
            "pack_sha256": digest(raw), "tampered_report_rejected": rejected}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="replay synthetic evidence and reject a changed report")
    create = commands.add_parser("pack", help="write an evidence pack to stdout")
    create.add_argument("files", nargs="+")
    create.add_argument("--ignore-unmatched", action="store_true")
    create.add_argument("--clock-uncertainty-ms", type=int, default=0)
    verify = commands.add_parser("verify", help="recompute a pack without opening original sources")
    verify.add_argument("file")
    verify.add_argument("--expect-sha256", help="optional trusted SHA-256 of the exact pack bytes")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = demo()
        elif args.command == "pack":
            if len(args.files) > engine.MAX_SOURCES:
                raise ReplayError("at most 64 sources")
            inputs, remaining = [], MAX_RAW_BYTES
            for name in args.files:
                data = read_workspace(name, remaining)
                inputs.append((name, data))
                remaining -= len(data)
            result = make_pack(inputs, args.ignore_unmatched, args.clock_uncertainty_ms)
        else:
            raw = read_workspace(args.file, MAX_PACK_BYTES)
            if args.expect_sha256 is not None:
                if not re.fullmatch(r"[0-9a-f]{64}", args.expect_sha256):
                    raise ReplayError("expected hash must be 64 lowercase hex digits")
                if digest(raw) != args.expect_sha256:
                    raise ReplayError("pack does not match expected SHA-256")
            result = verify_pack(load_pack(raw))
            result["pack_sha256"] = digest(raw)
        sys.stdout.buffer.write(canonical(result) + b"\n")
        return 0
    except (OSError, ReplayError, engine.TimelineError, ValueError, RecursionError) as exc:
        print("timeline-replay: " + engine.visible(str(exc)), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
