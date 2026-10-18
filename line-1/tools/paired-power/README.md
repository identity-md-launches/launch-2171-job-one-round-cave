# Paired Power

Plan how many independent, matched binary cases to collect **before** measuring
your systems. This complements Paired Verdict and Candidate Ladder: the older
tools analyze observations; this tool calculates rejection probabilities under
explicit hypothetical assumptions. Python 3.10+ and the standard library only.
Copy this folder anywhere; the planner requires no other line's code or assets.

From the repository root, see a complete prospective plan:

```sh
python3 -B line-1/tools/paired-power/paired_power.py --demo
```

When tried, the hypothetical three-candidate plan assumed a 30% probability of
disagreement and a 75% candidate win share among disagreements. At familywise
alpha 0.05 it used the conservative per-comparison threshold 1/60. Its numerical
two-sided rejection probabilities were:

| Paired cases | Rejection probability |
| ---: | ---: |
| 40 | 0.164944452451 |
| 80 | 0.455665648763 |
| 120 | 0.702689497130 |
| 200 | 0.932561993210 |
| 400 | 0.999348789411 |

The smallest **evaluated** size meeting the 80% target was 200. This does not
mean 200 is the minimum possible size. No real system was measured by this demo.
The saved `demo-plan.json` is the actual CLI output, not benchmark evidence.

For your own assumptions:

```sh
python3 -B line-1/tools/paired-power/paired_power.py --sizes 80,120,160,200 --discordance 0.30 --win-share 0.75 --candidates 3 --alpha 0.05 --target 0.80
```

`--discordance q` is the probability that baseline and candidate disagree on a
case; `--win-share theta` is the chance the candidate passes among those
disagreements. Thus candidate-only wins have probability `q*theta`, baseline-only
wins `q*(1-theta)`, and concordant cases `1-q`. The expected pass-rate difference
is `q*(2*theta-1)`. A pass-rate difference alone does not determine power; two
benchmarks with the same difference can have different disagreement rates.
Choose plausible assumptions prospectively, using a separate pilot if available,
and try sensitivity plans. Values do not come from, or verify, live measurements.

The model is `D ~ Binomial(n,q)` and `W | D=d ~ Binomial(d,theta)`. For every
possible `d`, the code determines the exact integer rejection region of the
two-sided conditional McNemar test:

```text
min(1, 2 * sum(comb(d,j), j=0..min(w,d-w)) / 2**d) <= alpha / m
```

It averages that region's probability over both binomial distributions. The
threshold comparison is exact integer arithmetic, including equality. Probability
weights use floating point recurrences expanded from the binomial mode, avoiding
endpoint underflow. Displayed probabilities are numerical estimates without a
certified error bound. The target comparison is numerical too; avoid treating
machine-level differences at the boundary as a guarantee.

With one candidate this is power for Paired Verdict's fixed-size test. With
`m > 1`, `alpha/m` is a Bonferroni threshold. Any candidate passing it also passes
the full family's Holm rule, so this supplies a conservative **per-candidate**
power bound for Candidate Ladder. It is not exact Holm power, which requires a
joint candidate-outcome model, nor the probability that all or any candidates
will reject. Set `m` to the full planned family, including candidates absent from
this particular planning calculation. Repeat planning with each candidate's
own prospective assumptions if they differ.

Two-sided rejection may favor the baseline. JSON separately reports
`probability_reject_with_candidate_ahead`; for `theta < 0.5`, high two-sided
power can mainly detect a worse candidate. `theta=0.5` represents equal
discordance; `q=0` gives no possible rejection. The model leaves the division
of concordant cases into both-pass and both-fail unspecified, so it cannot
recover either system's marginal pass rate.

Prespecify a fixed final sample size, case set, pass rule, baseline, complete
candidate family and alpha before observing results. Case independence and
constant pair probabilities are assumptions. This planner does not support
interim testing, outcome-dependent stopping, retries counted as independent
cases, correlated cases, or equivalence claims. Its canonical assumptions
SHA-256 makes equivalent inputs reproducible; it cannot prove when a plan was
chosen or that anyone followed it. Preserve the plan alongside raw observations.

Limits: 1–64 distinct sizes, each 1–2000 pairs; 1–16 candidates; alpha from
0.000001 through 0.2 inclusive; `q` and `theta` from 0 through 1 inclusive;
target strictly between 0 and 1. Decimal strings are at most 48 characters and
have at most 18 fractional decimal places. Non-endpoint probabilities rounding
to 0 or 1 in floating point are rejected. Inputs and computation are bounded.
Output is JSON on stdout. A valid plan exits 0 even when no evaluated size
meets the target (the selected size is then `null`); invalid input exits 2 with
an error on stderr and no partial JSON. The planner reads no input files,
environment, accounts or network and writes no files.

Verification:

```sh
python3 -B -m unittest discover -s line-1/tools/paired-power -v
```

All 11 tests passed locally. Independent exhaustive three-outcome sequences
through eight cases check unconditional and candidate-ahead probabilities;
direct binomial formulas check mode-expanded weights; Candidate Ladder's actual
source checks exact decision agreement for every possible win count through
70 discordances. The optional predecessor integration skips if this folder is
copied alone. Other tests cover exact alpha boundaries, deterministic endpoints,
label symmetry, multiplicity, null calibration through 2000 pairs, bounded
inputs, canonical hashes and CLI errors. The two unchanged predecessor suites
also passed (15 and 6 tests). These checks cover the exercised contract, not
experimental honesty or generalization.
