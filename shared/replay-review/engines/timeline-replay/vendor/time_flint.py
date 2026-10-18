#!/usr/bin/env python3
"""Build an auditable timeline from offset-aware ISO 8601 and epoch log records."""

import argparse
import hashlib
import json
import re
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ISO = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?)(Z|[+-]\d{2}:\d{2})$"
)
TEXT = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2}))(?:\s+|$)(.*)$"
)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_LINE_BYTES = 64 * 1024
MAX_LINES = 100000
MAX_SOURCES = 64
MAX_JSON_DEPTH = 64
DEMO = {
    "service.log": (
        "2026-10-18T10:00:00Z request accepted\n"
        "2026-10-18T10:00:02Z response completed\n"
    ),
    "queue.jsonl": (
        '{"timestamp":"2026-10-18T12:00+02:00","message":"queued near acceptance"}\n'
        '{"ts":1792317601500,"event":"worker began"}\n'
    ),
}


class TimelineError(ValueError):
    pass


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise TimelineError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def micros(dt):
    delta = dt.astimezone(timezone.utc) - EPOCH
    return ((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds)


MIN_MICROS = micros(datetime.min.replace(tzinfo=timezone.utc))
MAX_MICROS = micros(datetime.max.replace(tzinfo=timezone.utc))


def checked_interval(start, end):
    """Both endpoints must be printable UTC calendar instants, without clamping."""
    if not MIN_MICROS <= start < end <= MAX_MICROS:
        raise TimelineError("UTC interval endpoints must fit calendar years 0001 through 9999")
    return start, end


def utc_text(value):
    dt = EPOCH + timedelta(microseconds=value)
    return dt.isoformat(timespec="microseconds" if dt.microsecond else "seconds").replace("+00:00", "Z")


def visible(value):
    """Render untrusted log text without terminal control effects."""
    return json.dumps(value, ensure_ascii=True)[1:-1]


def parse_stamp(value):
    """Return UTC half-open interval in microseconds and its declared precision."""
    if isinstance(value, bool):
        raise TimelineError("boolean is not a timestamp")
    if isinstance(value, int):
        magnitude = abs(value)
        if 10 ** 9 <= magnitude < 10 ** 10:
            start, width, precision = value * 1000000, 1000000, "second"
        elif 10 ** 12 <= magnitude < 10 ** 13:
            start, width, precision = value * 1000, 1000, "millisecond"
        else:
            raise TimelineError("epoch integer must have 10 seconds or 13 milliseconds digits")
        start, end = checked_interval(start, start + width)
        return start, end, precision
    if not isinstance(value, str):
        raise TimelineError("timestamp must be ISO 8601 text or an integer epoch")
    match = ISO.fullmatch(value)
    if not match:
        raise TimelineError("timestamp needs T, explicit Z or ±HH:MM offset, and at most 6 fraction digits")
    body, offset = match.groups()
    try:
        dt = datetime.fromisoformat(body + ("+00:00" if offset == "Z" else offset))
    except ValueError as exc:
        raise TimelineError(f"invalid calendar time: {exc}") from exc
    # datetime.fromisoformat accepts offsets above 23 hours, which are not RFC 3339.
    if offset != "Z" and (int(offset[1:3]) > 23 or int(offset[4:]) > 59):
        raise TimelineError("UTC offset is outside ±23:59")
    fraction = body.partition(".")[2]
    if fraction:
        width, precision = 10 ** (6 - len(fraction)), f"{len(fraction)} fractional digit(s)"
    elif body.count(":") == 2:
        width, precision = 1000000, "second"
    else:
        width, precision = 60000000, "minute"
    try:
        start = micros(dt)
    except OverflowError as exc:
        raise TimelineError("timestamp converts outside UTC calendar years 0001 through 9999") from exc
    start, end = checked_interval(start, start + width)
    return start, end, precision


def reject_constant(value):
    raise TimelineError(f"nonstandard JSON number: {value}")


def check_json_depth(value):
    """Bound structured messages independently of the runtime recursion limit."""
    pending = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, (dict, list)):
            if depth > MAX_JSON_DEPTH:
                raise TimelineError(f"JSON containers exceed {MAX_JSON_DEPTH} levels of nesting")
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, depth + 1) for child in children)


def parse_line(raw, source, number):
    if raw.lstrip().startswith("{"):
        try:
            obj = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        except json.JSONDecodeError as exc:
            raise TimelineError(f"invalid JSON: {exc.msg}") from exc
        except (RecursionError, ValueError) as exc:
            if isinstance(exc, TimelineError):
                raise
            raise TimelineError("JSON exceeds supported nesting or numeric limits") from exc
        check_json_depth(obj)
        if not isinstance(obj, dict):
            raise TimelineError("JSONL event must be an object")
        keys = [k for k in ("timestamp", "time", "ts") if k in obj]
        if len(keys) != 1:
            raise TimelineError("JSONL event needs exactly one of timestamp, time, ts")
        stamp = obj[keys[0]]
        message = next((obj[k] for k in ("message", "msg", "event") if k in obj), None)
        if message is None:
            message = {k: v for k, v in obj.items() if k != keys[0]}
        if not isinstance(message, str):
            message = json.dumps(message, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    else:
        match = TEXT.fullmatch(raw)
        if not match:
            raise TimelineError("line needs an offset-aware ISO timestamp prefix or JSONL event")
        stamp, message = match.groups()
    start, end, precision = parse_stamp(stamp)
    return {
        "start_utc": utc_text(start),
        "end_utc_exclusive": utc_text(end),
        "precision": precision,
        "source": source,
        "line": number,
        "line_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "message": message,
        "_start": start,
        "_end": end,
    }


def build(inputs, ignore_unmatched=False, clock_uncertainty_ms=0):
    """Merge bytes with an optional asserted symmetric clock-error bound.

    The bound is an assumption supplied by the analyst, never inferred from logs.
    Reported intervals remain attached when adjusted intervals are requested.
    """
    if (isinstance(clock_uncertainty_ms, bool) or not isinstance(clock_uncertainty_ms, int)
            or not 0 <= clock_uncertainty_ms <= 86400000):
        raise TimelineError("clock uncertainty must be an integer from 0 to 86400000 milliseconds")
    uncertainty = clock_uncertainty_ms * 1000
    sources, events, errors, omitted = [], [], [], []
    total_bytes, total_lines, seen = 0, 0, set()
    for name, data in inputs:
        if not isinstance(name, str) or not isinstance(data, bytes):
            raise TimelineError("each source must have a text name and bytes content")
        if name in seen:
            raise TimelineError(f"duplicate source name: {name}")
        seen.add(name)
        total_bytes += len(data)
        if len(seen) > MAX_SOURCES:
            raise TimelineError(f"at most {MAX_SOURCES} sources are supported")
        if len(data) > MAX_FILE_BYTES or total_bytes > MAX_TOTAL_BYTES:
            raise TimelineError("input exceeds 8 MiB per source or 32 MiB total")
        sources.append({"source": name, "sha256": hashlib.sha256(data).hexdigest()})
        try:
            content = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            errors.append(f"{name}: invalid UTF-8 at byte {exc.start}")
            continue
        for number, physical_line in enumerate(content.split("\n"), 1):
            total_lines += 1
            if total_lines > MAX_LINES:
                raise TimelineError(f"input exceeds {MAX_LINES} physical lines")
            raw = physical_line.removesuffix("\r")
            if len(raw.encode("utf-8")) > MAX_LINE_BYTES:
                raise TimelineError(f"{name}:{number}: line exceeds 64 KiB")
            if not raw.strip():
                continue
            try:
                event = parse_line(raw, name, number)
            except TimelineError as exc:
                if ignore_unmatched:
                    omitted.append({
                        "source": name,
                        "line": number,
                        "line_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                        "reason": str(exc),
                    })
                else:
                    errors.append(f"{name}:{number}: {exc}")
                continue
            if uncertainty:
                # A failed model application is not an unmatched log line. Even
                # --ignore-unmatched must not silently drop valid edge events.
                start, end = checked_interval(event["_start"] - uncertainty,
                                              event["_end"] + uncertainty)
                event["reported_start_utc"] = event["start_utc"]
                event["reported_end_utc_exclusive"] = event["end_utc_exclusive"]
                event["start_utc"], event["end_utc_exclusive"] = utc_text(start), utc_text(end)
                event["_start"], event["_end"] = start, end
            events.append(event)
    if errors:
        raise TimelineError("\n".join(errors))
    events.sort(key=lambda e: (e["_start"], e["source"], e["line"]))
    group, furthest_end = 0, None
    for event in events:
        if furthest_end is None or event["_start"] >= furthest_end:
            group += 1
            furthest_end = event["_end"]
        else:
            furthest_end = max(furthest_end, event["_end"])
        event["overlap_group"] = group
        del event["_start"]
        del event["_end"]
    result = {"version": 1, "sources": sources, "events": events, "omitted": omitted}
    if uncertainty:
        result["version"] = 2
        result["clock_model"] = {
            "kind": "asserted_symmetric_bound",
            "uncertainty_ms": clock_uncertainty_ms,
            "assumption": "Each source clock differs from UTC by at most this bound at every event.",
            "precision_assumption": "Timestamps are truncated to their displayed precision.",
        }
    return result


def read_inputs(names, root=None):
    """Read explicit regular workspace files (or stdin), enforcing byte bounds."""
    root = Path.cwd().resolve() if root is None else Path(root).resolve()
    inputs, total = [], 0
    if len(names) > MAX_SOURCES:
        raise TimelineError(f"at most {MAX_SOURCES} sources are supported")
    for name in names:
        limit = min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total)
        if name == "-":
            data = sys.stdin.buffer.read(limit + 1)
        else:
            path = Path(name)
            path = (root / path).resolve() if not path.is_absolute() else path.resolve()
            if not path.is_relative_to(root):
                raise TimelineError(f"source resolves outside the current workspace: {name}")
            if not stat.S_ISREG(path.stat().st_mode):
                raise TimelineError(f"source must be a regular file: {name}")
            with path.open("rb") as stream:
                data = stream.read(limit + 1)
        if len(data) > limit:
            raise TimelineError(f"{name}: input exceeds 8 MiB per source or 32 MiB total")
        total += len(data)
        inputs.append((name, data))
    return inputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="UTF-8 logs or JSONL files; use - for stdin")
    parser.add_argument("--demo", action="store_true", help="analyze two embedded example logs")
    parser.add_argument("--json", action="store_true", help="emit deterministic machine-readable JSON")
    parser.add_argument("--ignore-unmatched", action="store_true", help="explicitly omit malformed/non-event lines")
    parser.add_argument("--clock-uncertainty-ms", type=int, default=0, metavar="MS",
                        help="assert a symmetric clock error bound (0..86400000 ms) for every source")
    args = parser.parse_args(argv)
    if args.demo and args.files:
        parser.error("--demo cannot be combined with files")
    if not args.demo and not args.files:
        parser.error("supply at least one file or --demo")
    if args.files.count("-") > 1:
        parser.error("stdin may be used only once")
    try:
        inputs = (
            [(name, data.encode("utf-8")) for name, data in DEMO.items()]
            if args.demo else
            read_inputs(args.files)
        )
        result = build(inputs, args.ignore_unmatched, args.clock_uncertainty_ms)
    except (OSError, TimelineError) as exc:
        print(f"time-flint: {visible(str(exc))}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        if "clock_model" in result:
            print(f"ASSUMPTION: every source clock is within ±{args.clock_uncertainty_ms} ms of UTC; "
                  "displayed intervals include this asserted bound.")
        print("GROUP  EARLIEST UTC                  LATEST UTC (EXCLUSIVE)        SOURCE:LINE  MESSAGE")
        for event in result["events"]:
            print(f"{event['overlap_group']:>5}  {event['start_utc']:<29} {event['end_utc_exclusive']:<29} "
                  f"{visible(event['source'])}:{event['line']}  {visible(event['message'])}")
        print("Each group connects events through interval overlap; some pairwise orders may still be certain.")
        for item in result["omitted"]:
            print(f"OMITTED {visible(item['source'])}:{item['line']}: {visible(item['reason'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
