"""Evidence/replay contract checks; synthetic logs only, standard library only."""
import base64
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import timeline_replay as t


class ReplayChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Path("test/scratch").mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.inputs = [("client.log", b"\xef\xbb\xbf2026-10-18T10:00:00Z caf\xc3\xa9\r\nnoise\r\n"),
                       ("server.jsonl", b'{"ts":1792317602000,"message":"done"}\n')]
        self.pack = t.make_pack(self.inputs, True, 750)

    def test_exact_bytes_and_assumptions_survive_roundtrip(self):
        pack = t.load_pack(t.canonical(self.pack))
        self.assertEqual([base64.b64decode(x["base64"]) for x in pack["inputs"]],
                         [data for _, data in self.inputs])
        result = t.verify_pack(pack)
        self.assertEqual(result, dict(verified=True, sources=2, events=2, omitted=1,
                                     clock_uncertainty_ms=750))
        self.assertEqual(pack["timeline"]["omitted"][0]["line"], 2)
        self.assertEqual(pack["timeline"]["events"][0]["reported_start_utc"],
                         "2026-10-18T10:00:00Z")

    def test_deterministic_serialization(self):
        self.assertEqual(t.canonical(self.pack), t.canonical(t.make_pack(self.inputs, True, 750)))

    def test_changed_source_bytes_are_rejected(self):
        self.pack["inputs"][0]["base64"] = base64.b64encode(b"changed").decode()
        with self.assertRaisesRegex(t.ReplayError, "source hash"):
            t.verify_pack(self.pack)

    def test_changed_source_and_updated_hash_still_fail_report(self):
        data = self.inputs[0][1].replace(b"caf\xc3\xa9", b"edited")
        self.pack["inputs"][0].update(base64=base64.b64encode(data).decode(), sha256=t.digest(data))
        with self.assertRaisesRegex(t.ReplayError, "exact replay"):
            t.verify_pack(self.pack)

    def test_report_tampering_including_bool_integer_confusion(self):
        for field, value in (("message", "invented"), ("line", True), ("overlap_group", 99),
                             ("end_utc_exclusive", "2026-10-18T10:00:00Z")):
            pack = copy.deepcopy(self.pack)
            pack["timeline"]["events"][0][field] = value
            with self.subTest(field=field), self.assertRaises(t.ReplayError):
                t.verify_pack(pack)

    def test_omission_removal_and_event_removal_are_rejected(self):
        for field in ("events", "omitted"):
            pack = copy.deepcopy(self.pack)
            pack["timeline"][field].pop()
            with self.subTest(field=field), self.assertRaises(t.ReplayError):
                t.verify_pack(pack)

    def test_changed_clock_assumption_is_rejected(self):
        self.pack["options"]["clock_uncertainty_ms"] = 0
        with self.assertRaisesRegex(t.ReplayError, "exact replay"):
            t.verify_pack(self.pack)

    def test_engine_mismatch_is_explicit(self):
        self.pack["engine_sha256"] = "incorrect"
        with self.assertRaisesRegex(t.ReplayError, "engine source hash"):
            t.verify_pack(self.pack)

    def test_names_are_never_opened_during_replay(self):
        # An impossible path remains just a citation. No attempted source-file read.
        pack = t.make_pack([("not-a-file/missing.log", b"2026-10-18T10:00Z event")])
        with patch.object(t, "read_workspace", side_effect=AssertionError("must not read source")):
            self.assertTrue(t.verify_pack(pack)["verified"])

    def test_unknown_keys_and_versions_are_rejected(self):
        for field, value in (("format", "timeline-replay/999"), ("extra", 1)):
            pack = copy.deepcopy(self.pack)
            pack[field] = value
            with self.subTest(field=field), self.assertRaises(t.ReplayError):
                t.verify_pack(pack)

    def test_strict_options(self):
        for field, value in (("ignore_unmatched", 1), ("clock_uncertainty_ms", True),
                             ("clock_uncertainty_ms", -1), ("clock_uncertainty_ms", 86400001)):
            pack = copy.deepcopy(self.pack)
            pack["options"][field] = value
            with self.subTest(value=value), self.assertRaises(t.ReplayError):
                t.verify_pack(pack)

    def test_duplicate_names_rejected_by_parser(self):
        with self.assertRaises(t.engine.TimelineError):
            t.make_pack([("a", b""), ("a", b"")])

    def test_bad_base64_and_noncanonical_padding_rejected(self):
        for value in ("%%%%", "Zh==", "Zg===", "\u2603"):
            pack = copy.deepcopy(self.pack)
            pack["inputs"][0]["base64"] = value
            with self.subTest(value=value), self.assertRaises(t.ReplayError):
                t.verify_pack(pack)

    def test_json_duplicate_keys_nan_invalid_utf8_and_depth(self):
        for raw in (b'{"format":1,"format":2}', b'{"a":NaN}', b'\xff',
                    b'[' * 70 + b'0' + b']' * 70):
            with self.subTest(raw=raw[:30]), self.assertRaises(t.ReplayError):
                t.load_pack(raw)

    def test_source_and_pack_budgets(self):
        with patch.object(t, "MAX_RAW_BYTES", 1):
            with self.assertRaises(t.ReplayError):
                t.make_pack(self.inputs, True)
            with self.assertRaises(t.ReplayError):
                t.verify_pack(self.pack)
        with patch.object(t, "MAX_PACK_BYTES", 10):
            with self.assertRaises(t.ReplayError):
                t.load_pack(b" " * 11)
            with self.assertRaises(t.ReplayError):
                t.make_pack(self.inputs, True)
        for inputs in ([], [("a", b"")] * 65):
            with self.assertRaises(t.ReplayError):
                t.make_pack(inputs)

    def test_empty_log_is_explicit_zero_events(self):
        result = t.verify_pack(t.make_pack([("empty.log", b"")]))
        self.assertEqual(result["events"], 0)
        self.assertEqual(result["sources"], 1)

    def test_workspace_limits_regular_files_and_symlinks(self):
        with tempfile.TemporaryDirectory(dir="test/scratch") as name:
            root = Path(name)
            path = root / "log"
            path.write_bytes(b"1234")
            self.assertEqual(t.read_workspace(path, 4), b"1234")
            with self.assertRaises(t.ReplayError):
                t.read_workspace(path, 3)
            with self.assertRaises(t.ReplayError):
                t.read_workspace(root, 4)
            # Test a path escape without reading any file outside the workspace.
            with self.assertRaises(t.ReplayError):
                t.read_workspace(Path.cwd().parent / "never-open-this", 4)
            link = root / "escape"
            link.symlink_to(Path.cwd().parent / "never-open-this")
            with self.assertRaises(t.ReplayError):
                t.read_workspace(link, 4)

    def test_cli_external_digest_rejects_changed_whitespace(self):
        with tempfile.TemporaryDirectory(dir="test/scratch") as name:
            path = Path(name) / "pack.json"
            raw = t.canonical(self.pack) + b"\n"
            path.write_bytes(raw + b" ")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(t.main(["verify", str(path), "--expect-sha256", t.digest(raw)]), 2)
            self.assertIn("expected SHA-256", stderr.getvalue())

    def test_cli_errors_are_escaped(self):
        stderr = io.StringIO()
        with patch.object(t, "read_workspace", side_effect=t.ReplayError("bad\x1b[31m\nline")), \
                contextlib.redirect_stderr(stderr):
            self.assertEqual(t.main(["verify", "missing"]), 2)
        self.assertNotIn("\x1b", stderr.getvalue())
        self.assertEqual(len(stderr.getvalue().splitlines()), 1)

    def test_demo_includes_rejection(self):
        self.assertTrue(t.demo()["tampered_report_rejected"])


if __name__ == "__main__":
    unittest.main()
