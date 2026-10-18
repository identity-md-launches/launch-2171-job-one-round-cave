# Exact quantities before trust

Unit Flint checks calculations with exact rational arithmetic and explicit
physical dimensions. It runs offline with Python 3.10+ and only the standard
library. It neither reads inputs from files nor contacts any service.

From the repository root, check a speed claim:

```sh
python3 -B line-4/tools/unit-flint/unit_flint.py '10 km / 2 h' --expect '5 km/h' --to m/s --json
```

This prints the exact `25/18 m/s`, reports `check.matches: true`, and exits 0.
An unequal claim exits 1; invalid syntax or incompatible units exits 2.
See [the tool README](tools/unit-flint/README.md) for the grammar, limits,
diagnostics, examples and one-command regression suite. The check verifies
the supplied arithmetic, not the truth of a measured input.

Mark 23 adds claim checking while preserving the line's original goal.
[WALL.md](WALL.md) records dimensions, formats and visual review;
[USED.md](USED.md) records the sources used.
