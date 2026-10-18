"""Independent finite-experiment oracles and CLI checks for prospective power."""

import importlib.util
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from fractions import Fraction as F

import paired_power as power


def oracle(n, q, theta, threshold):
    """Enumerate win/loss/concordance sequences, independently of the planner."""
    total = upper = F(0)
    probabilities = (q * theta, q * (1 - theta), 1 - q)
    for sequence in itertools.product(range(3), repeat=n):
        wins, losses = sequence.count(0), sequence.count(1)
        d = wins + losses
        p = min(F(1), F(2 * sum(math.comb(d, k) for k in range(min(wins, losses) + 1)), 2 ** d))
        if p <= threshold:
            weight = math.prod(probabilities[index] for index in sequence)
            total += weight
            if wins > losses:
                upper += weight
    return total, upper


class PairedPowerTests(unittest.TestCase):
    def test_exhaustive_three_outcome_experiments(self):
        for n in (1, 4, 6, 8):
            for q, theta in [(F(1), F(3, 4)), (F(1, 3), F(2, 3)), (F(2, 3), F(1, 4))]:
                for alpha, candidates in [(F(1, 5), 1), (F(1, 10), 2)]:
                    with self.subTest(n=n, q=q, theta=theta, candidates=candidates):
                        actual = power.plan([n], q, theta, alpha, candidates)['sizes'][0]
                        expected, ahead = oracle(n, q, theta, alpha / candidates)
                        self.assertAlmostEqual(actual['probability_reject_equal_discordance'], float(expected), places=13)
                        self.assertAlmostEqual(actual['probability_reject_with_candidate_ahead'], float(ahead), places=13)

    def test_exact_threshold_boundary(self):
        # Six discordances, all in one direction: exact two-sided p = 1/32.
        self.assertEqual(power.critical_lower_counts(6, F(1, 32))[6], 0)
        self.assertEqual(power.critical_lower_counts(6, F(1, 32) - F(1, 10**18))[6], -1)
        self.assertEqual(power.critical_lower_counts(0, F(1, 5)), [-1])

    def test_existing_candidate_ladder_rejection_agrees(self):
        source = Path(__file__).resolve().parents[1] / 'candidate-ladder' / 'candidate_ladder.py'
        if not source.exists():
            self.skipTest('optional predecessor integration requires the line-1 tree')
        spec = importlib.util.spec_from_file_location('previous_ladder', source)
        ladder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ladder)
        for threshold in (F(1, 20), F(1, 60), F(1, 1000000)):
            cutoffs = power.critical_lower_counts(70, threshold)
            for d in range(71):
                for wins in range(d + 1):
                    expected = ladder.exact_mcnemar(wins, d - wins) <= threshold
                    actual = min(wins, d - wins) <= cutoffs[d]
                    self.assertEqual(actual, expected)

    def test_binomial_weights_against_direct_formula(self):
        for n in range(31):
            for p in (F(0), F(1, 10), F(1, 2), F(9, 10), F(1)):
                actual = power.binomial_pmf(n, p)
                self.assertAlmostEqual(math.fsum(actual), 1.0, places=14)
                for k, item in enumerate(actual):
                    expected = math.comb(n, k) * p ** k * (1 - p) ** (n - k)
                    self.assertAlmostEqual(item, float(expected), places=14)

    def test_no_discordances_and_deterministic_directions(self):
        self.assertEqual(power.plan([100], F(0), F(3, 4))['sizes'][0]['probability_reject_equal_discordance'], 0)
        for share in (F(0), F(1)):
            result = power.plan([5, 6], F(1), share)['sizes']
            self.assertEqual([row['probability_reject_equal_discordance'] for row in result], [0, 1])
            self.assertEqual(result[1]['probability_reject_with_candidate_ahead'], float(share))

    def test_null_calibration_at_maximum_budget(self):
        result = power.plan([10, 100, 1000, 2000], F(3, 10), F(1, 2), candidates=16)
        for row in result['sizes']:
            self.assertLessEqual(row['probability_reject_equal_discordance'], 0.05 / 16 + 1e-14)
            self.assertGreaterEqual(row['probability_reject_equal_discordance'], 0)

    def test_label_symmetry_and_multiplicity(self):
        a = power.plan([40, 120], F(3, 10), F(3, 4))
        b = power.plan([40, 120], F(3, 10), F(1, 4))
        family = power.plan([40, 120], F(3, 10), F(3, 4), candidates=3)
        for left, right, corrected in zip(a['sizes'], b['sizes'], family['sizes']):
            self.assertAlmostEqual(left['probability_reject_equal_discordance'], right['probability_reject_equal_discordance'], places=14)
            self.assertLessEqual(corrected['probability_reject_equal_discordance'], left['probability_reject_equal_discordance'])
            self.assertAlmostEqual(left['probability_reject_with_candidate_ahead'] + right['probability_reject_with_candidate_ahead'], left['probability_reject_equal_discordance'], places=14)

    def test_known_demo_and_reproducibility_hash(self):
        a = power.plan([40, 80, 120, 200, 400], F(3, 10), F(3, 4), candidates=3)
        self.assertEqual(a['smallest_evaluated_size_meeting_target'], 200)
        self.assertAlmostEqual(a['sizes'][3]['probability_reject_equal_discordance'], 0.9325619932096577, places=13)
        self.assertEqual(a['comparison_threshold'], '1/60')
        b = power.plan([400, 200, 120, 80, 40], F(3, 10), F(3, 4), candidates=3)
        self.assertEqual(a, b)
        c = power.plan([40, 80, 120, 200, 400], F(3, 10), F(3, 4), candidates=2)
        self.assertNotEqual(a['assumptions_sha256'], c['assumptions_sha256'])
        self.assertIsNone(power.plan([1], F(1), F(1))['smallest_evaluated_size_meeting_target'])

    def test_invalid_probability_strings(self):
        for text in ('NaN', 'Infinity', '-0.1', '1.1', 'bad', '1e-99999999', '9' * 49):
            with self.subTest(text=text), self.assertRaises(power.PlanError):
                power.probability(text, 'test')
        self.assertEqual(power.probability('0', 'test'), 0)
        self.assertEqual(power.probability('1', 'test'), 1)
        self.assertEqual(power.probability('0.30', 'test'), F(3, 10))

    def test_invalid_plans(self):
        for sizes in ([], [0], [2001], [True], [10, 10], list(range(1, 66)), [1.5]):
            with self.subTest(sizes=sizes), self.assertRaises(power.PlanError):
                power.plan(sizes, F(1, 2), F(3, 4))
        for kwargs in ({'candidates': 0}, {'candidates': 17}, {'alpha': F(0)},
                       {'target': F(0)}, {'target': F(1)}, {'discordance': F(-1)},
                       {'win_share': F(1) - F(1, 10**18)}):
            args = dict(sizes=[10], discordance=F(1, 2), win_share=F(3, 4))
            args.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(power.PlanError):
                power.plan(**args)

    def test_cli_success_and_failure_contract(self):
        script = str(Path(power.__file__).resolve())
        good = subprocess.run([sys.executable, '-B', script, '--demo'], capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)['data_kind'], 'hypothetical_planning_demonstration')
        commands = [[], ['--demo', '--candidates', '3'],
                    ['--sizes', '2,2', '--discordance', '.3', '--win-share', '.75'],
                    ['--sizes', '1', '--discordance', '.3', '--win-share', 'NaN'],
                    ['--sizes', '1', '--discordance', '.3', '--win-share', '0.999999999999999999']]
        for args in commands:
            with self.subTest(args=args):
                bad = subprocess.run([sys.executable, '-B', script, *args], capture_output=True, text=True)
                self.assertEqual(bad.returncode, 2)
                self.assertEqual(bad.stdout, '')
                self.assertNotIn('Traceback', bad.stderr)


if __name__ == '__main__':
    unittest.main()
