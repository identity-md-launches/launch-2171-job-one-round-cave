#!/usr/bin/env python3
"""Exact, dimension-aware arithmetic for small measurements. No code execution."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import re
import sys


# Base dimensions: length, mass, time, data. Factors are exact base units.
Dimensions = tuple[int, int, int, int]
ZERO: Dimensions = (0, 0, 0, 0)
MAX_SOURCE = 4096
MAX_TOKENS = 256
MAX_DEPTH = 32
MAX_BITS = 2048
MAX_DIMENSION = 256


def unit(factor: str, dims: Dimensions) -> tuple[Fraction, Dimensions]:
    return Fraction(Decimal(factor)), dims


UNITS: dict[str, tuple[Fraction, Dimensions]] = {
    "m": unit("1", (1, 0, 0, 0)),
    "cm": unit("0.01", (1, 0, 0, 0)),
    "mm": unit("0.001", (1, 0, 0, 0)),
    "km": unit("1000", (1, 0, 0, 0)),
    "in": unit("0.0254", (1, 0, 0, 0)),
    "ft": unit("0.3048", (1, 0, 0, 0)),
    "mi": unit("1609.344", (1, 0, 0, 0)),
    "kg": unit("1", (0, 1, 0, 0)),
    "g": unit("0.001", (0, 1, 0, 0)),
    "mg": unit("0.000001", (0, 1, 0, 0)),
    "t": unit("1000", (0, 1, 0, 0)),
    "s": unit("1", (0, 0, 1, 0)),
    "ms": unit("0.001", (0, 0, 1, 0)),
    "min": unit("60", (0, 0, 1, 0)),
    "h": unit("3600", (0, 0, 1, 0)),
    "day": unit("86400", (0, 0, 1, 0)),
    "B": unit("1", (0, 0, 0, 1)),
    "KiB": unit("1024", (0, 0, 0, 1)),
    "MiB": unit("1048576", (0, 0, 0, 1)),
    "GiB": unit("1073741824", (0, 0, 0, 1)),
    "L": unit("0.001", (3, 0, 0, 0)),
    "mL": unit("0.000001", (3, 0, 0, 0)),
    "N": unit("1", (1, 1, -2, 0)),
    "J": unit("1", (2, 1, -2, 0)),
    "W": unit("1", (2, 1, -3, 0)),
}

BASE = ("m", "kg", "s", "B")
NUMBER = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9]*")


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    pos: int


@dataclass(frozen=True)
class Quantity:
    value: Fraction  # in base units
    dims: Dimensions


class UnitError(Exception):
    def __init__(self, message: str, pos: int):
        super().__init__(message)
        self.pos = pos


def tokenize(source: str) -> list[Token]:
    if len(source) > MAX_SOURCE:
        raise UnitError(f"expression exceeds {MAX_SOURCE} characters", MAX_SOURCE)
    tokens: list[Token] = []
    i = 0
    while i < len(source):
        if source[i].isspace():
            i += 1
            continue
        if len(tokens) >= MAX_TOKENS:
            raise UnitError(f"expression exceeds {MAX_TOKENS} tokens", i)
        match = NUMBER.match(source, i) or IDENT.match(source, i)
        if match:
            kind = "number" if NUMBER.fullmatch(match.group()) else "unit"
            tokens.append(Token(kind, match.group(), i))
            i = match.end()
            continue
        if source.startswith("**", i):
            tokens.append(Token("^", "**", i))
            i += 2
            continue
        if source[i] in "+-*/^()":
            tokens.append(Token(source[i], source[i], i))
            i += 1
            continue
        raise UnitError(f"unexpected character {source[i]!r}", i)
    tokens.append(Token("end", "", len(source)))
    return tokens


def dimensions(dims: Dimensions) -> str:
    parts = [f"{name}^{power}" if power != 1 else name
             for name, power in zip(BASE, dims) if power]
    return "*".join(parts) or "1"


class Parser:
    def __init__(self, source: str, target: bool = False):
        self.source = source
        self.tokens = tokenize(source)
        self.i = 0
        self.target = target
        self.depth = 0

    @staticmethod
    def bounded(q: Quantity, pos: int) -> Quantity:
        if max(q.value.numerator.bit_length(), q.value.denominator.bit_length()) > MAX_BITS:
            raise UnitError(f"exact value exceeds {MAX_BITS}-bit arithmetic budget", pos)
        if any(abs(d) > MAX_DIMENSION for d in q.dims):
            raise UnitError(f"dimension exceeds range -{MAX_DIMENSION}..{MAX_DIMENSION}", pos)
        return q

    @property
    def here(self) -> Token:
        return self.tokens[self.i]

    def take(self, kind: str) -> bool:
        if self.here.kind == kind:
            self.i += 1
            return True
        return False

    def parse(self) -> Quantity:
        result = self.add()
        if self.here.kind != "end":
            raise UnitError(f"unexpected {self.here.text!r}; an operator is required", self.here.pos)
        return result

    def add(self) -> Quantity:
        left = self.multiply()
        while self.here.kind in ("+", "-"):
            op = self.here
            if self.target:
                raise UnitError("a target unit cannot contain addition or subtraction", op.pos)
            self.i += 1
            right = self.multiply()
            if left.dims != right.dims:
                raise UnitError(
                    f"incompatible dimensions: {dimensions(left.dims)} and {dimensions(right.dims)}",
                    op.pos,
                )
            left = self.bounded(Quantity(
                left.value + (right.value if op.kind == "+" else -right.value), left.dims), op.pos)
        return left

    def multiply(self) -> Quantity:
        left = self.unary()
        while self.here.kind in ("*", "/"):
            op = self.here
            self.i += 1
            right = self.unary()
            if op.kind == "*":
                left = Quantity(left.value * right.value,
                                tuple(a + b for a, b in zip(left.dims, right.dims)))
            else:
                if right.value == 0:
                    raise UnitError("division by zero", op.pos)
                left = Quantity(left.value / right.value,
                                tuple(a - b for a, b in zip(left.dims, right.dims)))
            left = self.bounded(left, op.pos)
        return left

    def unary(self) -> Quantity:
        if self.depth >= MAX_DEPTH:
            raise UnitError(f"expression nesting exceeds {MAX_DEPTH} levels", self.here.pos)
        self.depth += 1
        try:
            return self._unary()
        finally:
            self.depth -= 1

    def _unary(self) -> Quantity:
        if self.here.kind in ("+", "-"):
            op = self.here
            self.i += 1
            q = self.unary()
            return Quantity(-q.value if op.kind == "-" else q.value, q.dims)
        return self.power()

    def power(self) -> Quantity:
        q = self.atom()
        if self.here.kind == "^":
            op = self.here
            self.i += 1
            exponent = self.unary()
            if exponent.dims != ZERO or exponent.value.denominator != 1:
                raise UnitError("exponent must be a dimensionless integer", op.pos)
            n = exponent.value.numerator
            if abs(n) > 12:
                raise UnitError("exponent exceeds the supported range -12..12", op.pos)
            if q.value == 0 and n < 0:
                raise UnitError("zero cannot have a negative exponent", op.pos)
            return self.bounded(Quantity(q.value ** n, tuple(d * n for d in q.dims)), op.pos)
        return q

    def atom(self) -> Quantity:
        token = self.here
        if self.take("("):
            q = self.add()
            if not self.take(")"):
                raise UnitError("missing closing parenthesis", self.here.pos)
            return q
        if self.take("number"):
            if len(token.text) > 80:
                raise UnitError("number is too long", token.pos)
            try:
                number = Decimal(token.text)
                if abs(number.as_tuple().exponent) > 200:
                    raise UnitError("decimal exponent exceeds range -200..200", token.pos)
                if abs(number.adjusted()) > 100:
                    raise UnitError("number magnitude exceeds 10^100", token.pos)
                value = Fraction(number)
            except InvalidOperation:
                raise UnitError("invalid decimal number", token.pos) from None
            if self.here.kind == "unit":
                label = self.here
                self.i += 1
                factor, dims = self.lookup(label)
                return Quantity(value * factor, dims)
            return Quantity(value, ZERO)
        if self.take("unit"):
            factor, dims = self.lookup(token)
            return Quantity(factor, dims)
        raise UnitError("expected a number, unit, or parenthesized expression", token.pos)

    @staticmethod
    def lookup(token: Token) -> tuple[Fraction, Dimensions]:
        try:
            return UNITS[token.text]
        except KeyError:
            raise UnitError(f"unknown unit {token.text!r}", token.pos) from None


def exact_decimal(value: Fraction) -> str:
    """Return a finite decimal if possible, otherwise an exact fraction."""
    numerator, denominator = value.numerator, value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        return f"{numerator}/{value.denominator}"
    places = max(twos, fives)
    scaled = abs(numerator) * (2 ** (places - twos)) * (5 ** (places - fives))
    digits = str(scaled).zfill(places + 1)
    result = digits if places == 0 else f"{digits[:-places]}.{digits[-places:]}".rstrip("0").rstrip(".")
    return ("-" if numerator < 0 else "") + result


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("expression", help='e.g. "1.5 km + 350 m"')
    cli.add_argument("--to", metavar="UNIT", help='target unit, e.g. "m" or "km/h"')
    cli.add_argument("--json", action="store_true", help="emit machine-readable exact result")
    cli.add_argument("--expect", metavar="EXPRESSION",
                     help="check exact equality to a claimed quantity (exit 1 if unequal)")
    args = cli.parse_args(argv)
    source = args.expression
    try:
        result = Parser(source).parse()
        expected = None
        difference = None
        if args.expect is not None:
            source = args.expect
            expected = Parser(source).parse()
            if expected.dims != result.dims:
                raise UnitError(
                    f"expected dimension {dimensions(expected.dims)} does not match result {dimensions(result.dims)}",
                    0,
                )
            difference = Parser.bounded(
                Quantity(result.value - expected.value, result.dims), 0)
        if args.to:
            source = args.to
            target = Parser(source, target=True).parse()
            if target.value <= 0:
                raise UnitError("target unit must have a positive scale", 0)
            if target.dims != result.dims:
                raise UnitError(
                    f"target dimension {dimensions(target.dims)} does not match result {dimensions(result.dims)}",
                    0,
                )
            value = Parser.bounded(Quantity(result.value / target.value, result.dims), 0).value
            label = args.to
        else:
            value = result.value
            label = dimensions(result.dims)
    except UnitError as exc:
        print(f"unit-flint: {exc}\n  {source}\n  {' ' * exc.pos}^", file=sys.stderr)
        return 2
    output = {
        "expression": args.expression,
        "value": exact_decimal(value),
        "unit": label,
        "base_value": exact_decimal(result.value),
        "base_unit": dimensions(result.dims),
        "dimensions": dict(zip(("length", "mass", "time", "data"), result.dims)),
    }
    if expected is not None:
        output["check"] = {
            "expression": args.expect,
            "expected_base_value": exact_decimal(expected.value),
            "difference_base_value": exact_decimal(difference.value),
            "base_unit": dimensions(result.dims),
            "matches": difference.value == 0,
        }
    if args.json:
        print(json.dumps(output, separators=(",", ":")))
    else:
        print(f"{output['value']} {label}")
        if expected is not None:
            verdict = "match" if difference.value == 0 else "mismatch"
            print(f"{verdict}: expected {args.expect}; result - expected = "
                  f"{exact_decimal(difference.value)} {dimensions(result.dims)}")
    return 1 if expected is not None and difference.value != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
