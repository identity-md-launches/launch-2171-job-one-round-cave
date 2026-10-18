"""Offline arithmetic and adversarial input checks; no files or network read."""
import contextlib
from fractions import Fraction
import io
import json
import random
import unittest

from unit_flint import Parser, UnitError, exact_decimal, main


class UnitFlintTests(unittest.TestCase):
    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(args)
        return status, out.getvalue(), err.getvalue()

    def test_exact_claims_across_units(self):
        for expression, claim in [
            ('0.1 + 0.2', '0.3'),
            ('10 km / 2 h', '5 km/h'),
            ('1 L', '1000 mL'),
            ('1 J / 1 s', '1 W'),
            ('1 in', '2.54 cm'),
            ('-1 m', '-100 cm'),
            ('1 m - 100 cm', '0 km'),
            ('1 m / 3 s', '100 cm / 3 s'),
            ('2 * m^2', '20000 * cm^2'),
        ]:
            with self.subTest(expression=expression, claim=claim):
                status, out, err = self.run_cli([
                    '--json', '--expect=' + claim, '--', expression])
                self.assertEqual(status, 0)
                self.assertEqual(err, '')
                check = json.loads(out)['check']
                self.assertIs(check['matches'], True)
                self.assertEqual(check['difference_base_value'], '0')

    def test_mismatch_is_exact_and_machine_readable(self):
        for expression, claim, difference in [
            ('0.1 + 0.2', '0.30000000000000001', '-0.00000000000000001'),
            ('1 m / 3 s', '0.3333333333333333 m/s', '1/30000000000000000'),
            ('2 m^2', '2 * m^2', '2'),
            ('0 s', '1 s', '-1'),
        ]:
            with self.subTest(expression=expression):
                status, out, err = self.run_cli([
                    expression, '--expect=' + claim, '--json'])
                self.assertEqual(status, 1)
                self.assertEqual(err, '')
                check = json.loads(out)['check']
                self.assertIs(check['matches'], False)
                self.assertEqual(check['difference_base_value'], difference)

    def test_claim_errors_have_no_partial_result(self):
        for claim, message in [
            ('1 s', 'expected dimension s does not match result m'),
            ('0', 'expected dimension 1 does not match result m'),
            ('', 'expected a number'),
            ('3 unknown', 'unknown unit'),
            ('1 / 0', 'division by zero'),
            ('-' * 1100 + '1', 'tokens'),
            ('(' * 40 + '1' + ')' * 40, 'nesting'),
            ('(1e100)^12', 'arithmetic budget'),
        ]:
            with self.subTest(claim=claim[:40]):
                status, out, err = self.run_cli(['1 m', '--expect=' + claim, '--json'])
                self.assertEqual(status, 2)
                self.assertEqual(out, '')
                self.assertIn(message, err)
                self.assertIn('\n  ' + claim + '\n', err)
                self.assertNotIn('Traceback', err)

    def test_claim_and_conversion_are_independent(self):
        status, out, err = self.run_cli([
            '10 km / 2 h', '--expect', '5 km/h', '--to', 'm/s', '--json'])
        self.assertEqual((status, err), (0, ''))
        result = json.loads(out)
        self.assertEqual(result['value'], '25/18')
        self.assertEqual(result['check']['expected_base_value'], '25/18')
        status, out, err = self.run_cli([
            '1 m', '--expect', '100 cm', '--to', 's', '--json'])
        self.assertEqual(status, 2)
        self.assertEqual(out, '')
        self.assertIn('\n  s\n', err)

    def test_claim_plain_output_and_legacy_shape(self):
        status, out, err = self.run_cli(['1 m', '--expect', '100 cm'])
        self.assertEqual((status, err), (0, ''))
        self.assertEqual(out, '1 m\nmatch: expected 100 cm; result - expected = 0 m\n')
        status, out, err = self.run_cli(['1 m', '--expect', '2 m'])
        self.assertEqual((status, err), (1, ''))
        self.assertIn('mismatch:', out)
        status, out, err = self.run_cli(['1 m', '--json'])
        self.assertEqual((status, err), (0, ''))
        self.assertEqual(set(json.loads(out)), {
            'expression', 'value', 'unit', 'base_value', 'base_unit', 'dimensions'})

    def test_seeded_claim_conversion_checks(self):
        rng = random.Random(738)
        for _ in range(150):
            amount = rng.randrange(-10000, 10001)
            expression = f'{amount} cm'
            claim = f'{amount}/100 * m'
            status, out, err = self.run_cli([
                '--expect=' + claim, '--json', '--', expression])
            self.assertEqual((status, err), (0, ''))
            self.assertIs(json.loads(out)['check']['matches'], True)
            status, out, err = self.run_cli([
                '--expect=' + f'{amount + 1}/100 * m', '--json', '--', expression])
            self.assertEqual((status, err), (1, ''))
            self.assertEqual(json.loads(out)['check']['difference_base_value'], '-0.01')

    def test_exact_arithmetic_and_conversions(self):
        for expression, expected, dims in [
            ('0.1 + 0.2', Fraction(3, 10), (0, 0, 0, 0)),
            ('1.5 km + 350 m', Fraction(1850), (1, 0, 0, 0)),
            ('10 km / 2 h', Fraction(25, 18), (1, 0, -1, 0)),
            ('1 L - 1000 mL', Fraction(0), (3, 0, 0, 0)),
            ('1 J / 1 s', Fraction(1), (2, 1, -3, 0)),
            ('1 in / 1 ft', Fraction(1, 12), (0, 0, 0, 0)),
            ('2 * m^2', Fraction(2), (2, 0, 0, 0)),
            ('2 m^2', Fraction(4), (2, 0, 0, 0)),
            ('-2^2', Fraction(-4), (0, 0, 0, 0)),
            ('2^3^2', Fraction(512), (0, 0, 0, 0)),
        ]:
            with self.subTest(expression=expression):
                q = Parser(expression).parse()
                self.assertEqual((q.value, q.dims), (expected, dims))

    def test_invalid_arithmetic(self):
        for expression in ('2 m + 3 s', '1 / 0', '0^-1', 'm^0.5',
                           'm^s', 'm^13', 'unknown', '1;print(1)', '()', '1 2'):
            with self.subTest(expression=expression):
                with self.assertRaises(UnitError):
                    Parser(expression).parse()

    def test_all_resource_limits(self):
        for expression, message in [
            ('-' * 1100 + '1', 'tokens'),
            ('-' * 33 + '1', 'nesting'),
            ('(' * 40 + '1' + ')' * 40, 'nesting'),
            ('2^' * 40 + '1', 'nesting'),
            (' ' * 4097, 'characters'),
            ('1+' * 128 + '1', 'tokens'),
            ('(1e100)^12', 'arithmetic budget'),
            ('((1e-100)^12)', 'arithmetic budget'),
            ('((m^12)^12)^2', 'dimension'),
            ('0e-999999999', 'decimal exponent'),
            ('0e999999999', 'decimal exponent'),
        ]:
            with self.subTest(expression=expression[:40]):
                with self.assertRaisesRegex(UnitError, message):
                    Parser(expression).parse()

    def test_boundary_acceptance_and_depth_reset(self):
        self.assertEqual(Parser('-' * 31 + '1').parse().value, -1)
        self.assertEqual(Parser('1+' * 127 + '1').parse().value, 128)
        self.assertEqual(Parser(' ' * 4095 + '1').parse().value, 1)
        self.assertEqual(Parser('(1e100)^6').parse().value, 10**600)
        parser = Parser('(' * 40 + '1' + ')' * 40)
        with self.assertRaises(UnitError):
            parser.parse()
        self.assertEqual(parser.depth, 0)

    def test_cli_json_and_regular_error(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(main(['10 km / 2 h', '--to', 'm/s', '--json']), 0)
        self.assertEqual(json.loads(out.getvalue())['value'], '25/18')
        self.assertEqual(err.getvalue(), '')
        for args in [ ['--', '-' * 1100 + '1'], ['1 m', '--to', 's'],
                      ['1e100', '--to', '(1e-100)^6'], ['1', '--to', 'm+m'] ]:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(main(args), 2)
            self.assertEqual(out.getvalue(), '')
            self.assertIn('unit-flint:', err.getvalue())
            self.assertNotIn('Traceback', err.getvalue())

    def test_exact_formatting_roundtrip(self):
        rng = random.Random(737)
        for _ in range(500):
            value = Fraction(rng.randrange(-100000, 100001), rng.randrange(1, 1000))
            self.assertEqual(Fraction(exact_decimal(value)), value)
        self.assertEqual(exact_decimal(Fraction(1, 8)), '0.125')
        self.assertEqual(exact_decimal(Fraction(1, 3)), '1/3')

    def test_seeded_invalid_input_is_bounded(self):
        rng = random.Random(737)
        for _ in range(1000):
            source = ''.join(rng.choice('0129e+-*/^() ms.') for _ in range(rng.randrange(100)))
            try:
                q = Parser(source).parse()
                exact_decimal(q.value)
            except UnitError:
                pass


if __name__ == '__main__':
    unittest.main()
