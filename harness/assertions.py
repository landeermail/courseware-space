"""Domain-independent, executable physics assertion primitives."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Dimension:
    """SI base dimensions used by the harness (mass, length, time)."""

    mass: int = 0
    length: int = 0
    time: int = 0

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(self.mass + other.mass, self.length + other.length, self.time + other.time)

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return Dimension(self.mass - other.mass, self.length - other.length, self.time - other.time)

    def __pow__(self, power: int) -> "Dimension":
        return Dimension(self.mass * power, self.length * power, self.time * power)


DIMENSIONLESS = Dimension()
MASS = Dimension(mass=1)
LENGTH = Dimension(length=1)
TIME = Dimension(time=1)
VELOCITY = LENGTH / TIME
ACCELERATION = LENGTH / (TIME**2)
FORCE = MASS * ACCELERATION
ENERGY = FORCE * LENGTH


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    message: str
    actual: Any = None
    expected: Any = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AssertionFailure(ValueError):
    def __init__(self, report: "AssertionReport") -> None:
        self.report = report
        failed = ", ".join(check.name for check in report.checks if not check.passed)
        super().__init__(f"物理断言失败：{failed}")


@dataclass(frozen=True)
class AssertionReport:
    domain: str
    checks: tuple[Check, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def require(self) -> "AssertionReport":
        if not self.passed:
            raise AssertionFailure(self)
        return self

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "passed": self.passed,
            "checks": [check.as_dict() for check in self.checks],
            "failed": [check.name for check in self.checks if not check.passed],
        }


def close_check(
    name: str,
    actual: object,
    expected: float,
    *,
    rel_tol: float = 1e-7,
    abs_tol: float = 1e-8,
) -> Check:
    valid = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(float(actual))
    passed = valid and math.isclose(float(actual), float(expected), rel_tol=rel_tol, abs_tol=abs_tol)
    return Check(name, passed, f"{name}: actual={actual!r}, expected={expected:.12g}", actual, expected)


def equal_check(name: str, actual: object, expected: object) -> Check:
    return Check(name, actual == expected, f"{name}: actual={actual!r}, expected={expected!r}", actual, expected)


def true_check(name: str, condition: object, message: str) -> Check:
    return Check(name, condition is True, message, condition, True)


def finite_check(name: str, values: Iterable[object]) -> Check:
    items = list(values)
    passed = bool(items) and all(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
        for value in items
    )
    return Check(name, passed, f"{name}: 所有状态量必须是有限数值", items if not passed else len(items), "finite")


def dimension_check(name: str, left: Dimension, right: Dimension) -> Check:
    return Check(name, left == right, f"{name}: left={left}, right={right}", asdict(left), asdict(right))


def report(domain: str, checks: Iterable[Check]) -> AssertionReport:
    return AssertionReport(domain, tuple(checks))
