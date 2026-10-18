#!/usr/bin/env python3
"""Replay an evidence pack, then review raw logs and decoded JSON Unicode."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
# Only fixed, shipped modules are imported. Pack paths are inert citations.
sys.path.insert(0, str(HERE / 'engines/timeline-replay'))
import timeline_replay as replay


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


json_lantern = module('replay_json_lantern', HERE / 'engines/json-lantern/json_lantern.py')
unit = module('replay_unit_flint', HERE / 'engines/unit-flint/unit_flint.py')
lantern = json_lantern.lantern
MAX_JSON_LINES = 2000
MAX_RETAINED_REVIEWS = 100
FINDINGS_PER_REVIEW = 50


def clock_bound(expression):
    try:
        quantity = unit.Parser(expression).parse()
    except unit.UnitError as exc:
        raise ValueError(f'clock bound character {exc.pos + 1}: {exc}') from exc
    if quantity.dims != (0, 0, 1, 0):
        raise ValueError('clock bound must have time dimensions')
    value = quantity.value * 1000
    if not 0 <= value <= 86400000 or value.denominator != 1:
        raise ValueError('clock bound must be exact whole milliseconds between 0 ms and 1 day')
    return value.numerator


def check_pin(raw, expected):
    if expected is not None:
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('expected SHA-256 must be 64 lowercase hex digits')
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('pack does not match independently supplied SHA-256')


def review_bytes(raw, expected=None):
    """Verify before scanning; original paths are never opened during replay."""
    check_pin(raw, expected)
    pack = replay.load_pack(raw)
    verified = replay.verify_pack(pack)
    reviews, review_count, finding_count, errors, json_lines = [], 0, 0, 0, 0
    listings_truncated = False

    def retain(report, source, kind, line=None):
        nonlocal review_count, finding_count, errors, listings_truncated
        review_count += 1
        finding_count += report.get('finding_count', 0)
        errors += int('error_escaped' in report)
        listings_truncated |= report.get('truncated', False)
        # Keep interesting reviews first; clean results are counted in totals.
        if report.get('finding_count', 0) or 'error_escaped' in report:
            if len(reviews) < MAX_RETAINED_REVIEWS:
                reviews.append({'source_escaped': lantern.escaped(source),
                                'domain': kind, 'physical_line': line, 'report': report})
            else:
                listings_truncated = True

    for entry in pack['inputs']:
        data = base64.b64decode(entry['base64'], validate=True)
        name = entry['source']
        retain(lantern.scan(data, name, FINDINGS_PER_REVIEW), name, 'raw-source')
        # Match Time Flint's BOM and CRLF interpretation, keeping physical lines.
        # Inspect *all* JSON-looking lines, even ones omitted by the timeline.
        for number, physical in enumerate(data.decode('utf-8-sig').split('\n'), 1):
            line = physical.removesuffix('\r')
            if not line.lstrip().startswith('{'):
                continue
            json_lines += 1
            if json_lines > MAX_JSON_LINES:
                raise ValueError(f'review exceeds {MAX_JSON_LINES} JSON-looking lines; split the evidence')
            encoded = line.encode('utf-8')
            try:
                report = json_lantern.review(encoded, '<physical-json-line>', FINDINGS_PER_REVIEW)
            except (ValueError, UnicodeError, RecursionError) as exc:
                report = {'error_escaped': lantern.escaped(str(exc)),
                          'sha256': hashlib.sha256(encoded).hexdigest(),
                          'assessment': 'review-incomplete'}
            retain(report, name, 'decoded-json-line', number)
    return {
        'schema_version': 1, 'tool': 'replay-review',
        'pack_sha256': hashlib.sha256(raw).hexdigest(),
        'digest_pin_checked': expected is not None,
        'replay': verified,
        'assessment': 'review-required' if finding_count or errors else 'no-covered-patterns-found',
        'finding_count': finding_count, 'review_errors': errors,
        'review_count': review_count, 'json_lines_checked': json_lines,
        'listings_truncated': listings_truncated,
        'reviews': reviews,
        'limitations': [
            'Replay verifies consistency, not truthful logs, completeness, author identity or collection time.',
            'A digest only authenticates bytes when obtained independently from a trusted source.',
            'Unicode triage is heuristic; a clean report is not a safety verdict.',
            'Raw and decoded findings may describe the same character; counts are not unique incidents.',
            'Decoded offsets are local to a string; structural paths are local to the cited physical JSON line.',
            'Only JSON-looking object lines are decoded; plain log messages are scanned as raw text.',
            'At most 100 interesting reviews, with 50 findings each, are retained; truncation is explicit.',
            'Clock bounds are analyst assumptions; overlap does not establish causal order.',
            'Packs contain unredacted original logs. Choose non-sensitive evidence before packing.',
        ],
    }


def demo():
    inputs = [
        ('service.log', b'2026-10-18T10:00:00Z accepted\r\n'),
        ('queue.jsonl', br'{"ts":1792317602000,"message":"owner and \u043ewner","owner":1,"\u043ewner":2}' + b'\n' +
         br'{"ts":1792317603000,"message":"hidden \u202eevil\u202c","owner":1,"owner":2}' + b'\n'),
    ]
    pack = replay.make_pack(inputs, True, clock_bound('0.75 s'))
    raw = replay.canonical(pack) + b'\n'
    result = review_bytes(raw, hashlib.sha256(raw).hexdigest())
    changed = replay.load_pack(raw)
    changed['timeline']['events'][0]['message'] = 'altered conclusion'
    try:
        review_bytes(replay.canonical(changed))
    except replay.ReplayError:
        result['tampered_timeline_rejected'] = True
    else:
        raise ValueError('demo failed to reject tampering')
    result['data_kind'] = 'synthetic_demonstration'
    return result


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest='command', required=True)
    commands.add_parser('demo', help='synthetic cross-line evidence, no file input')
    create = commands.add_parser('pack', help='write a Timeline Replay compatible pack to stdout')
    create.add_argument('files', nargs='+')
    create.add_argument('--clock-bound', default='0 ms')
    create.add_argument('--ignore-unmatched', action='store_true')
    verify = commands.add_parser('review', help='verify and review one workspace pack')
    verify.add_argument('file')
    verify.add_argument('--expect-sha256')
    args = cli.parse_args(argv)
    try:
        if args.command == 'demo':
            result = demo()
        elif args.command == 'pack':
            bound = clock_bound(args.clock_bound)  # fail before reading evidence
            if not 1 <= len(args.files) <= replay.engine.MAX_SOURCES:
                raise ValueError('supply 1..64 sources')
            inputs, remaining = [], replay.MAX_RAW_BYTES
            for name in args.files:
                data = replay.read_workspace(name, remaining)
                inputs.append((name, data))
                remaining -= len(data)
            result = replay.make_pack(inputs, args.ignore_unmatched, bound)
        else:
            raw = replay.read_workspace(args.file, replay.MAX_PACK_BYTES)
            result = review_bytes(raw, args.expect_sha256)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False))
        return 1 if args.command == 'review' and result['assessment'] == 'review-required' else 0
    except (OSError, ValueError, unit.UnitError, RecursionError) as exc:
        print('replay-review: ' + lantern.escaped(str(exc)), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
