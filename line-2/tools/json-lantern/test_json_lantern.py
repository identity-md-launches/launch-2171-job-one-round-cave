import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

import json_lantern as tool


class JsonReviewTests(unittest.TestCase):
    def test_demo_uncovers_what_raw_scanner_cannot(self):
        self.assertEqual(tool.lantern.scan(tool.DEMO)["finding_count"], 0)
        result = tool.review(tool.DEMO)
        self.assertEqual(result["finding_count"], 6)
        self.assertEqual(result["sha256"], hashlib.sha256(tool.DEMO).hexdigest())
        self.assertFalse(result["truncated"])

    def test_repeated_keys_preserve_both_values(self):
        result = tool.review(br'{"x":"\u202e","x":"\u200b"}')
        decoded = [f for f in result["findings"] if f["domain"] == "decoded-string"]
        self.assertEqual([f["location"] for f in decoded],
                         [[{"pair": 0, "role": "value"}], [{"pair": 1, "role": "value"}]])
        duplicate = next(f for f in result["findings"] if f.get("rule") == "duplicate-key")
        self.assertEqual(duplicate["first_location"], [{"pair": 0, "role": "key"}])

    def test_escaped_key_equal_to_literal_is_duplicate(self):
        result = tool.review(br'{"owner":0,"\u006fwner":1}')
        self.assertEqual(result["finding_count"], 1)
        self.assertEqual(result["findings"][0]["rule"], "duplicate-key")

    def test_key_comparison_is_object_local(self):
        result = tool.review(br'[{"owner":0},{"owner":1}]')
        self.assertEqual(result["finding_count"], 0)

    def test_whole_keys_not_only_identifier_tokens(self):
        result = tool.review(br'{"pay-owner":0,"pay-\u043ewner":1}')
        collision = next(f for f in result["findings"] if f.get("rule") == "lookalike-key-collision")
        self.assertEqual(collision["skeleton"], "pay-owner")
        self.assertEqual(collision["first_escaped"], "pay-owner")

    def test_nested_path_and_decoded_offsets_are_not_raw_offsets(self):
        raw = br'{"a/b~":[{"":"\ud83d\udc38\r\n\u00e9\u202e"}]}'
        result = tool.review(raw)
        finding = result["findings"][0]
        self.assertEqual(finding["location"], [{"pair": 0, "role": "value"},
                                               {"index": 0}, {"pair": 0, "role": "value"}])
        evidence = finding["evidence"]
        self.assertEqual((evidence["line"], evidence["column"], evidence["byte_offset"]), (2, 2, 8))

    def test_literal_control_has_separate_raw_and_decoded_evidence(self):
        result = tool.review(('"' + chr(0x202E) + '"').encode())
        findings = result["findings"]
        self.assertEqual([f["domain"] for f in findings], ["decoded-string", "raw-json"])
        self.assertEqual([f["evidence"]["byte_offset"] for f in findings], [0, 1])

    def test_global_truncation_still_counts_every_domain(self):
        full = tool.review(tool.DEMO)
        for limit in (1, 2, 5):
            result = tool.review(tool.DEMO, max_findings=limit)
            self.assertEqual(result["finding_count"], full["finding_count"])
            self.assertEqual(len(result["findings"]), limit)
            self.assertTrue(result["truncated"])
        result = tool.review(json.dumps(chr(0x202E) * 30).encode(), max_findings=2)
        self.assertEqual(result["finding_count"], 30)
        self.assertEqual(len(result["findings"]), 2)

    def test_malformed_nonfinite_and_surrogates_fail(self):
        for raw in (b'{', b'{"x":1,}', b'"\xff"', b'NaN', b'Infinity', b'-Infinity',
                    br'"\ud800"', br'{"\udfff":0}', b'\xef\xbb\xbf{}', b'{} {}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                tool.review(raw)

    def test_container_depth_bound_ignores_string_contents(self):
        self.assertEqual(tool.review(b'"' + b'[' * 100 + b'"')["finding_count"], 0)
        tool.review(b'[' * tool.MAX_DEPTH + b'0' + b']' * tool.MAX_DEPTH)
        with self.assertRaisesRegex(ValueError, "nesting"):
            tool.review(b'[' * (tool.MAX_DEPTH + 1) + b'0' + b']' * (tool.MAX_DEPTH + 1))

    def test_node_budget_is_fatal_instead_of_partial_clean_result(self):
        with self.assertRaisesRegex(ValueError, "value count"):
            tool.review(b'[' + b'0,' * tool.MAX_NODES + b'0]')

    def test_large_numbers_are_opaque_and_never_rounded(self):
        for raw in (b'1e999999999', b'9' * 5000, b'{"x":-0.0,"y":1e-9999}'):
            self.assertEqual(tool.review(raw)["finding_count"], 0)

    def test_evidence_is_ascii_after_json_decoding(self):
        result = tool.review(br'{"\u202e":"\u001b"}', source="bad" + chr(0x202E))
        serialized = json.dumps(result, ensure_ascii=True)
        self.assertTrue(serialized.isascii())
        decoded = json.loads(serialized)
        self.assertEqual(decoded["source"], r"bad\u202e")
        self.assertNotIn(chr(0x202E), str(decoded))
        self.assertNotIn(chr(27), str(decoded))

    def test_invalid_limits_and_size(self):
        for limit in (True, 0, -1, 1001):
            with self.assertRaises(ValueError):
                tool.review(b'{}', max_findings=limit)
        with self.assertRaises(ValueError):
            tool.review(b' ' * (tool.MAX_BYTES + 1))

    def test_scalar_and_empty_containers_are_valid(self):
        for raw in (b'{}', b'[]', b'null', b'true', b'false', b'12', b'"hello"'):
            self.assertEqual(tool.review(raw)["finding_count"], 0)

    def test_workspace_escape_rejected_before_open(self):
        with self.assertRaises(ValueError):
            tool.lantern.workspace_file(Path.cwd().parent / "not-an-input.json")

    def test_cli_demo_and_missing_input(self):
        demo = subprocess.run([sys.executable, "-B", str(Path(tool.__file__)), "--demo"],
                              capture_output=True)
        self.assertEqual(demo.returncode, 0)
        self.assertEqual(json.loads(demo.stdout)["finding_count"], 6)
        missing = subprocess.run([sys.executable, "-B", str(Path(tool.__file__)),
                                  "--file", "test/scratch/not-present.json"], capture_output=True)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("error", json.loads(missing.stdout))
        self.assertFalse(missing.stderr)


if __name__ == "__main__":
    unittest.main()
