#!/usr/bin/env python3
"""Plan fixed-size paired binary benchmarks before observing their outcomes."""

import argparse
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation
from fractions import Fraction


MAX_CASES = 2000
MAX_SIZES = 64
MAX_CANDIDATES = 16


class PlanError(ValueError):
    """A planning assumption is invalid or exceeds the computation budget."""


def probability(text, label, minimum=Fraction(0), maximum=Fraction(1)):
    """Parse bounded decimal assumptions without rounding test thresholds."""
    if not isinstance(text, str) or len(text) > 48:
        raise PlanError(f'{label} must be a decimal of at most 48 characters')
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise PlanError(f'{label} must be a finite decimal') from exc
    if not value.is_finite() or value < 0 or value > 1:
        raise PlanError(f'{label} must be between {minimum} and {maximum}')
    # Reject extreme exponent representations before constructing a huge rational.
    if value and value.as_tuple().exponent < -18:
        raise PlanError(f'{label} supports at most 18 decimal places')
    result = Fraction(value)
    if not minimum <= result <= maximum:
        raise PlanError(f'{label} must be between {minimum} and {maximum}')
    return result


def validate_sizes(sizes):
    if not isinstance(sizes, (list, tuple)) or not 1 <= len(sizes) <= MAX_SIZES:
        raise PlanError(f'provide 1 to {MAX_SIZES} distinct planned sizes')
    if any(type(n) is not int or not 1 <= n <= MAX_CASES for n in sizes):
        raise PlanError(f'each planned size must be an integer from 1 through {MAX_CASES}')
    if len(set(sizes)) != len(sizes):
        raise PlanError('planned sizes must be distinct')
    return sorted(sizes)


def critical_lower_counts(maximum, threshold):
    """Largest k with 2*sum(comb(d,j), j<=k)/2**d <= threshold, or -1.

    All comparisons use integers. The two tails are disjoint for threshold < 1.
    This matches the exact two-sided conditional McNemar rule of the older tools.
    """
    cutoffs = []
    for d in range(maximum + 1):
        term = total = 1
        cutoff = -1
        denominator = 1 << d
        for k in range(d // 2 + 1):
            if 2 * total * threshold.denominator > threshold.numerator * denominator:
                break
            cutoff = k
            term = term * (d - k) // (k + 1)
            total += term
        cutoffs.append(cutoff)
    return cutoffs


def binomial_pmf(n, p):
    """Normalized floating point Bin(n,p), expanded from its mode.

    Relative weights avoid underflow of the endpoint probability for large n.
    Values far below machine precision can still underflow; power is numerical.
    """
    result = [0.0] * (n + 1)
    if p == 0 or p == 1:
        result[n if p == 1 else 0] = 1.0
        return result
    p = float(p)
    mode = min(n, int((n + 1) * p))
    result[mode] = 1.0
    odds = p / (1 - p)
    for k in range(mode, n):
        result[k + 1] = result[k] * ((n - k) / (k + 1)) * odds
    for k in range(mode, 0, -1):
        result[k - 1] = result[k] * (k / (n - k + 1)) / odds
    normalizer = math.fsum(result)
    return [value / normalizer for value in result]


def conditional_rejections(cutoffs, win_share):
    values = []
    favorable = []
    for d, cutoff in enumerate(cutoffs):
        if cutoff < 0:
            values.append(0.0)
            favorable.append(0.0)
            continue
        pmf = binomial_pmf(d, win_share)
        lower = math.fsum(pmf[:cutoff + 1])
        upper = math.fsum(pmf[d - cutoff:])
        values.append(min(1.0, lower + upper))
        favorable.append(upper)
    return values, favorable


def plan(sizes, discordance, win_share, alpha=Fraction(1, 20), candidates=1,
         target=Fraction(4, 5)):
    sizes = validate_sizes(sizes)
    if type(candidates) is not int or not 1 <= candidates <= MAX_CANDIDATES:
        raise PlanError(f'candidate family size must be 1 through {MAX_CANDIDATES}')
    for label, value in [('discordance', discordance), ('win share', win_share), ('target', target)]:
        if not isinstance(value, Fraction) or not 0 <= value <= 1:
            raise PlanError(f'{label} must be an exact rational probability')
        if value not in (0, 1) and not 0 < float(value) < 1:
            raise PlanError(f'{label} is too close to an endpoint for floating point planning')
    if not isinstance(alpha, Fraction) or not Fraction(1, 1000000) <= alpha <= Fraction(1, 5):
        raise PlanError('alpha must be from 0.000001 through 0.2')
    if target in (0, 1):
        raise PlanError('target must be strictly between zero and one')
    threshold = alpha / candidates
    cutoffs = critical_lower_counts(max(sizes), threshold)
    conditional, favorable = conditional_rejections(cutoffs, win_share)
    rows = []
    for n in sizes:
        weights = binomial_pmf(n, discordance)
        rejection = min(1.0, max(0.0, math.fsum(a * b for a, b in zip(weights, conditional))))
        upper = min(rejection, max(0.0, math.fsum(a * b for a, b in zip(weights, favorable))))
        rows.append({
            'paired_cases': n,
            'expected_discordant_pairs': n * float(discordance),
            'probability_reject_equal_discordance': rejection,
            'probability_reject_with_candidate_ahead': upper,
            'meets_rejection_target_numerically': rejection >= float(target),
        })
    assumptions = {
        'planned_sizes': sizes,
        'probability_pair_is_discordant': str(discordance),
        'probability_candidate_wins_given_discordance': str(win_share),
        'familywise_alpha': str(alpha),
        'planned_candidate_count': candidates,
        'target_rejection_probability': str(target),
    }
    canonical = json.dumps(assumptions, sort_keys=True, separators=(',', ':')).encode('utf-8')
    qualifying = [row['paired_cases'] for row in rows if row['meets_rejection_target_numerically']]
    return {
        'schema_version': 1,
        'method': 'fixed-size exact two-sided conditional McNemar rejection region; numerical unconditional probability',
        'assumptions': assumptions,
        'assumptions_sha256': hashlib.sha256(canonical).hexdigest(),
        'comparison_threshold': str(threshold),
        'multiplicity_policy': ('single comparison' if candidates == 1 else
                                'Bonferroni alpha/m: conservative per-candidate power bound for the full Holm family'),
        'candidate_minus_baseline_expected_percentage_points': 100 * float(discordance * (2 * win_share - 1)),
        'smallest_evaluated_size_meeting_target': min(qualifying) if qualifying else None,
        'sizes': rows,
        'limitations': [
            'Planning assumptions are supplied guesses, not estimated or observed benchmark evidence.',
            'Independent identically distributed matched binary cases and one fixed final analysis are assumed.',
            'Two-sided rejection can favor either system; inspect candidate-ahead probability separately.',
            'For multiple candidates this is per-candidate power, not probability all or any candidates win.',
            'Bonferroni bounds Holm power without a joint model; it does not calculate exact Holm power.',
            'The selected size is smallest only among evaluated sizes, not a guaranteed global minimum.',
            'Planning several sizes is not permission to test repeatedly or stop after significance.',
            'Exact integer rejection thresholds; floating point power has no certified numerical error bound.',
            'Concordant pass/fail composition and marginal pass rates are not identified by this model.',
            'The assumptions hash is a reproducibility fingerprint, not a timestamp or preregistration proof.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='show an explicitly hypothetical prospective plan')
    parser.add_argument('--sizes', help='comma-separated fixed sizes; each 1 through 2000, at most 64')
    parser.add_argument('--discordance', help='assumed probability baseline and candidate disagree')
    parser.add_argument('--win-share', help='assumed candidate win probability conditional on disagreement')
    parser.add_argument('--alpha', default='0.05', help='familywise significance threshold')
    parser.add_argument('--candidates', type=int, default=1, help='total planned comparisons, 1 through 16')
    parser.add_argument('--target', default='0.8', help='desired two-sided rejection probability')
    args = parser.parse_args(argv)
    try:
        if args.demo:
            if (args.sizes is not None or args.discordance is not None or args.win_share is not None
                    or args.alpha != '0.05' or args.candidates != 1 or args.target != '0.8'):
                raise PlanError('--demo fixes all assumptions; use explicit planning arguments to change them')
            result = plan([40, 80, 120, 200, 400], Fraction(3, 10), Fraction(3, 4), candidates=3)
            result['data_kind'] = 'hypothetical_planning_demonstration'
        else:
            if args.sizes is None or args.discordance is None or args.win_share is None:
                raise PlanError('provide --sizes, --discordance and --win-share, or use --demo')
            if len(args.sizes) > 512:
                raise PlanError('size list exceeds 512 characters')
            try:
                sizes = [int(value) for value in args.sizes.split(',')]
            except ValueError as exc:
                raise PlanError('sizes must be comma-separated integers') from exc
            result = plan(sizes, probability(args.discordance, 'discordance'),
                          probability(args.win_share, 'win share'),
                          probability(args.alpha, 'alpha', Fraction(1, 1000000), Fraction(1, 5)),
                          args.candidates, probability(args.target, 'target'))
            result['data_kind'] = 'user_assumed_prospective_plan'
    except (PlanError, ValueError, OverflowError) as exc:
        parser.exit(2, f'error: {exc}\n')
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
