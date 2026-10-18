import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import replay_review as r


class ReplayReviewTests(unittest.TestCase):
    def pack(self, data=b'2026-10-18T10:00:00Z ordinary\n', omit=False):
        return r.replay.make_pack([('evidence.log', data)], omit, 0)

    def raw(self, pack):
        return r.replay.canonical(pack) + b'\n'

    def test_demo_reviews_omitted_duplicate_and_decoded_controls(self):
        result = r.demo()
        self.assertTrue(result['replay']['verified'])
        self.assertEqual(result['replay']['events'], 2)
        self.assertEqual(result['replay']['omitted'], 1)
        self.assertEqual(result['json_lines_checked'], 2)
        self.assertTrue(result['tampered_timeline_rejected'])
        self.assertTrue(result['digest_pin_checked'])
        evidence = json.dumps(result)
        self.assertIn('duplicate-key', evidence)
        self.assertIn('bidi-control', evidence)
        self.assertIn('lookalike-key-collision', evidence)

    def test_clean_pack_no_patterns(self):
        result = r.review_bytes(self.raw(self.pack()))
        self.assertEqual(result['assessment'], 'no-covered-patterns-found')
        self.assertEqual(result['finding_count'], 0)
        self.assertFalse(result['digest_pin_checked'])

    def test_missing_original_never_opened(self):
        pack = r.replay.make_pack([('../missing/source.log', b'2026-10-18T10:00:00Z ok')])
        result = r.review_bytes(self.raw(pack))
        self.assertTrue(result['replay']['verified'])

    def test_altered_timeline_rejected_before_review(self):
        pack = self.pack()
        pack['timeline']['events'][0]['message'] = 'replaced'
        with patch.object(r.lantern, 'scan', side_effect=AssertionError('scan must not run')):
            with self.assertRaises(r.replay.ReplayError):
                r.review_bytes(self.raw(pack))

    def test_altered_embedded_bytes_rejected(self):
        pack = self.pack()
        pack['inputs'][0]['base64'] = base64.b64encode(b'replaced').decode()
        with self.assertRaises(r.replay.ReplayError):
            r.review_bytes(self.raw(pack))

    def test_correct_and_wrong_independent_pins(self):
        raw = self.raw(self.pack())
        self.assertTrue(r.review_bytes(raw, hashlib.sha256(raw).hexdigest())['digest_pin_checked'])
        for pin in ['0'*64, 'xyz', 'A'*64]:
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                r.review_bytes(raw, pin)

    def test_pin_binds_whitespace(self):
        raw = self.raw(self.pack())
        with self.assertRaises(ValueError):
            r.review_bytes(raw + b' ', hashlib.sha256(raw).hexdigest())

    def test_duplicate_pack_fields_rejected(self):
        raw = self.raw(self.pack()).replace(b'"format":', b'"format":"other","format":', 1)
        with self.assertRaises(ValueError):
            r.review_bytes(raw)

    def test_decoded_findings_keep_physical_line(self):
        data = b'\xef\xbb\xbf\r\n' + br'{"ts":1792317602000,"message":"hidden \u202eevil\u202c"}' + b'\r\n'
        result = r.review_bytes(self.raw(self.pack(data)))
        reviews = [v for v in result['reviews'] if v['domain'] == 'decoded-json-line']
        self.assertEqual([v['physical_line'] for v in reviews], [2])
        self.assertEqual(reviews[0]['report']['finding_count'], 2)
        self.assertEqual(result['finding_count'], 3)  # raw BOM plus decoded bidi pair

    def test_invalid_omitted_json_is_incomplete(self):
        data = b'2026-10-18T10:00:00Z ok\n{broken\n'
        result = r.review_bytes(self.raw(self.pack(data, True)))
        self.assertEqual(result['review_errors'], 1)
        self.assertEqual(result['assessment'], 'review-required')
        self.assertEqual(result['replay']['omitted'], 1)

    def test_bounded_json_review_never_claims_clean(self):
        data = b'\n'.join([b'{"ts":1792317602000,"message":"ok"}'] * 3)
        with patch.object(r, 'MAX_JSON_LINES', 2):
            with self.assertRaisesRegex(ValueError, 'JSON-looking lines'):
                r.review_bytes(self.raw(self.pack(data)))

    def test_truncated_review_counts_all_findings(self):
        data = (br'{"ts":1792317602000,"message":"\u202e"}' + b'\n') * 3
        with patch.object(r, 'MAX_RETAINED_REVIEWS', 1):
            result = r.review_bytes(self.raw(self.pack(data)))
        self.assertTrue(result['listings_truncated'])
        self.assertEqual(result['finding_count'], 3)
        self.assertEqual(len(result['reviews']), 1)

    def test_exact_clock_quantity(self):
        for quantity in ['750 ms', '0.75 s', '1 s - 250 ms']:
            self.assertEqual(r.clock_bound(quantity), 750)
        for quantity in ['1 m', '0', '0.1 ms', '-1 s', '2 day']:
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                r.clock_bound(quantity)

    def test_cli_exit_contract_and_line3_interoperability(self):
        scratch = Path('test/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        script = str(Path(r.__file__))
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            log = Path(directory) / 'source.log'
            log.write_bytes(br'{"ts":1792317602000,"message":"\u202e"}' + b'\n')
            command = [sys.executable, '-B', script]
            packed = subprocess.run(command + ['pack', '--clock-bound', '0.75 s', str(log)], capture_output=True)
            self.assertEqual(packed.returncode, 0, packed.stderr)
            packfile = Path(directory) / 'pack.json'
            packfile.write_bytes(packed.stdout)
            log.unlink()
            reviewed = subprocess.run(command + ['review', str(packfile)], capture_output=True)
            self.assertEqual(reviewed.returncode, 1, reviewed.stderr)
            self.assertTrue(json.loads(reviewed.stdout)['replay']['verified'])
            # The unchanged upstream CLI can independently replay our pack.
            upstream = subprocess.run([sys.executable, '-B', 'line-3/tools/timeline-replay/timeline_replay.py',
                                       'verify', str(packfile)], capture_output=True)
            self.assertEqual(upstream.returncode, 0, upstream.stderr)
            invalid = subprocess.run(command + ['review', str(packfile), '--expect-sha256', '0'*64], capture_output=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(invalid.stdout, b'')

    def test_source_snapshots_are_exact(self):
        here = Path(r.__file__).parent
        records = json.loads((here / 'provenance.json').read_text())
        for row in records:
            raw = Path(row['snapshot']).read_bytes()
            self.assertEqual(raw, Path(row['source']).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])


if __name__ == '__main__':
    unittest.main()
