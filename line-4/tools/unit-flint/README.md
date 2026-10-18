# Unit Flint

Check arithmetic on measurements with exact rational values and explicit dimensions. The command accepts decimal quantities, parentheses, `+`, `-`, `*`, `/`, and integer powers (`^` or `**`). Addition and subtraction require matching dimensions; conversion requires a matching target unit. It evaluates its own small expression grammar and never executes Python code.

Run from the repository root:

```sh
python3 line-4/tools/unit-flint/unit_flint.py '1.5 km + 350 m' --to m
```

When tried locally, that command printed `1850 m`. The command `python3 line-4/tools/unit-flint/unit_flint.py '2 m + 3 s'` exited with an incompatible-dimensions error pointing to the `+`. Use `--json` for an exact machine-readable value, base value, and dimension vector. A repeating value is printed as an exact fraction. Supported units are `mm cm m km in ft mi`, `mg g kg t`, `ms s min h day`, `B KiB MiB GiB`, plus `mL L N J W`. Compound units use arithmetic, for example `10 km / 2 h --to 'm/s'`.

This first piece does not handle offset temperatures, currencies or exchange rates, uncertainty, or arbitrary named units. The magnitude of each input number and each exponent is bounded so accidental huge calculations fail quickly. It uses only Python's standard library and makes no network requests.

## Bounded calculation revision (mark 22)

The gathering's report of an uncaught recursion error is fixed. Inputs now have
limits of 4,096 characters, 256 tokens, and 32 active recursive grammar levels
(parentheses, unary signs and exponent expressions share this budget). Each
exact intermediate numerator and denominator is limited to 2,048 bits; each
dimension exponent must stay within -256..256. Decimal exponents must be within
-200..200, including zero-valued decimals. Existing number-length, magnitude
and integer-power limits still apply. The conversion result shares the arithmetic
budget. Exceeding any budget produces `UnitError`; the CLI prints a location and
exits 2. These are deliberate limits, even if cancellation could make the final
answer small. They bound this calculator's work, not an arbitrary Python caller.

One command demonstrates both ordinary calculations and the repaired failure:

```sh
python3 -B -m unittest discover -s line-4/tools/unit-flint -v
```

Tried locally: all seven tests passed, including the reported 1,100 unary minus
signs, deeply nested parentheses/powers, over-budget rational results and target
conversion, 500 exact formatting round trips, and 1,000 deterministic parser
probes. The documented distance command still prints `1850 m`; speed remains
the exact fraction `25/18 m/s`. These checks establish the covered behavior,
not exhaustive parser correctness or a real-world measurement claim.

**Notation:** `2 m^2` means `(2 m)^2`, which is four square metres in this
grammar. Write `2 * m^2` for two square metres. Use `--` before an expression
beginning with several minus signs so argparse treats it as an expression.
There are no file inputs, environment lookups, network requests or dependencies.

## Exact claim checking (mark 23)

Check a result somebody proposes before trusting it:

```sh
python3 -B line-4/tools/unit-flint/unit_flint.py '10 km / 2 h' --expect '5 km/h' --to m/s --json
```

Tried locally: exit **0**, value `25/18 m/s`, and `check.matches: true`.
Changing the claim to `6 km/h` gives exit **1**, `matches: false`, and exact
`difference_base_value: "-5/18"` in `m*s^-1`. The difference always means
**result minus expected**, in base units, regardless of `--to`.

`--expect` accepts the same bounded grammar as the calculation. The quantities
must have identical dimensions; even `0 m` and `0 s` are incompatible.
Exit **2** means invalid syntax, incompatible dimensions, invalid conversion,
or an exceeded arithmetic budget, and emits a diagnostic on stderr with no
partial stdout. A malformed expectation points into the expectation; a bad
conversion points into the target. Both the expectation and subtraction use
the existing resource budgets. `--expect=''` is an error, not a skipped check.

This checks exact equality, with no tolerance or rounding. Thus `0.1 + 0.2`
matches `0.3`, but `1 m / 3 s` does not match `0.3333333333333333 m/s`.
It checks what the supplied expressions say, not whether a measurement,
physical assumption, or unit choice is correct. No live token valuation or
currency arithmetic is involved.

Without `--expect`, the existing output and exit behavior are unchanged.
With it, JSON gains one `check` object containing the claim (`expression`),
`expected_base_value`, `difference_base_value`, `base_unit`, and boolean
`matches`. Exact values are strings, including rational fractions. Plain
output adds a readable match/mismatch line. For a negative expectation use
`--expect='-1 m'`; for a negative positional expression, put options first
and use `--` before the expression.

Run all regression checks with the unittest command above. All **13 tests**
passed locally: the seven existing tests plus six claim-check tests covering
mixed units, derived dimensions, exact fractions, negative and zero values,
rounded claims, parser budgets, diagnostics, conversion, compatibility, and
300 seeded matching/mismatching CLI evaluations. The tests call `main()` with
captured streams; real subprocess exit codes were also checked separately.
