"""Sports betting middle payoff and probability helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, lgamma, log
from statistics import NormalDist


class BetSide(str, Enum):
    """Supported side types for over/under betting legs."""

    OVER = "over"
    UNDER = "under"


@dataclass(frozen=True)
class BetLeg:
    """One over/under betting leg."""

    side: BetSide
    line: float
    odds_decimal: float
    stake: float
    book: str = ""
    label: str = ""


@dataclass(frozen=True)
class PayoffPoint:
    """Profit and loss for one possible settled outcome."""

    outcome: float
    over_profit: float
    under_profit: float
    total_profit: float
    state: str


@dataclass(frozen=True)
class MiddleAnalysis:
    """Payoff profile for buying an over/under interval."""

    over_leg: BetLeg
    under_leg: BetLeg
    payoff_points: list[PayoffPoint]
    middle_outcomes: list[float]

    @property
    def outcomes(self) -> list[float]:
        return [point.outcome for point in self.payoff_points]

    @property
    def middle_width(self) -> float:
        return max(self.under_leg.line - self.over_leg.line, 0.0)

    @property
    def total_stake(self) -> float:
        return self.over_leg.stake + self.under_leg.stake

    @property
    def lower_tail_profit(self) -> float:
        return self.under_leg.stake * (self.under_leg.odds_decimal - 1.0) - self.over_leg.stake

    @property
    def upper_tail_profit(self) -> float:
        return self.over_leg.stake * (self.over_leg.odds_decimal - 1.0) - self.under_leg.stake

    @property
    def middle_profit(self) -> float:
        return (
            self.over_leg.stake * (self.over_leg.odds_decimal - 1.0)
            + self.under_leg.stake * (self.under_leg.odds_decimal - 1.0)
        )

    @property
    def max_profit(self) -> float:
        return max(point.total_profit for point in self.payoff_points)

    @property
    def max_loss(self) -> float:
        return min(point.total_profit for point in self.payoff_points)


@dataclass(frozen=True)
class ExpectedValueSummary:
    """Probability-weighted summary of a middle payoff profile."""

    expected_profit: float
    expected_return_on_stake: float
    probability_middle: float
    probability_profit: float
    probability_loss: float
    covered_probability: float


def american_to_decimal(odds: float) -> float:
    """Convert American odds to decimal odds."""

    if odds >= 100:
        return 1.0 + odds / 100.0
    if odds <= -100:
        return 1.0 + 100.0 / abs(odds)
    raise ValueError("American odds must be at least +100 or no greater than -100.")


def decimal_to_american(odds: float) -> int:
    """Convert decimal odds to the nearest American odds quote."""

    _validate_decimal_odds(odds)
    if odds >= 2.0:
        return round((odds - 1.0) * 100.0)
    return round(-100.0 / (odds - 1.0))


def decimal_to_implied_probability(odds: float) -> float:
    """Convert decimal odds to an implied probability before removing vig."""

    _validate_decimal_odds(odds)
    return 1.0 / odds


def balanced_stakes(
    *,
    total_stake: float,
    over_odds_decimal: float,
    under_odds_decimal: float,
) -> tuple[float, float]:
    """Return over and under stakes that balance tail profit on both sides."""

    if total_stake <= 0:
        raise ValueError("total_stake must be greater than zero.")
    _validate_decimal_odds(over_odds_decimal)
    _validate_decimal_odds(under_odds_decimal)

    odds_sum = over_odds_decimal + under_odds_decimal
    over_stake = total_stake * under_odds_decimal / odds_sum
    under_stake = total_stake * over_odds_decimal / odds_sum
    return over_stake, under_stake


def build_middle_analysis(
    *,
    over_leg: BetLeg,
    under_leg: BetLeg,
    min_outcome: float,
    max_outcome: float,
    step: float = 1.0,
) -> MiddleAnalysis:
    """Build a payoff profile for a long over/under middle."""

    _validate_leg(over_leg, expected_side=BetSide.OVER)
    _validate_leg(under_leg, expected_side=BetSide.UNDER)
    outcomes = build_outcome_grid(
        min_outcome=min_outcome,
        max_outcome=max_outcome,
        step=step,
    )
    payoff_points = [
        PayoffPoint(
            outcome=outcome,
            over_profit=leg_profit(over_leg, outcome),
            under_profit=leg_profit(under_leg, outcome),
            total_profit=leg_profit(over_leg, outcome) + leg_profit(under_leg, outcome),
            state=_classify_outcome(outcome, over_leg=over_leg, under_leg=under_leg),
        )
        for outcome in outcomes
    ]
    middle_outcomes = [
        point.outcome
        for point in payoff_points
        if point.state == "middle"
    ]
    return MiddleAnalysis(
        over_leg=over_leg,
        under_leg=under_leg,
        payoff_points=payoff_points,
        middle_outcomes=middle_outcomes,
    )


def build_outcome_grid(
    *,
    min_outcome: float,
    max_outcome: float,
    step: float,
) -> list[float]:
    """Build an inclusive outcome grid."""

    if step <= 0:
        raise ValueError("step must be greater than zero.")
    if min_outcome > max_outcome:
        raise ValueError("min_outcome cannot exceed max_outcome.")

    count = int(round((max_outcome - min_outcome) / step)) + 1
    if count < 2:
        raise ValueError("outcome grid must contain at least two points.")
    return [round(min_outcome + index * step, 8) for index in range(count)]


def leg_profit(leg: BetLeg, outcome: float) -> float:
    """Calculate net profit for one betting leg and settled outcome."""

    _validate_leg(leg)
    result = _leg_result(leg, outcome)
    if result == "win":
        return leg.stake * (leg.odds_decimal - 1.0)
    if result == "loss":
        return -leg.stake
    return 0.0


def normal_probabilities(
    outcomes: list[float],
    *,
    mean: float,
    stdev: float,
    step: float,
) -> dict[float, float]:
    """Approximate discrete outcome probabilities from a normal distribution."""

    if stdev <= 0:
        raise ValueError("stdev must be greater than zero.")
    if step <= 0:
        raise ValueError("step must be greater than zero.")

    distribution = NormalDist(mu=mean, sigma=stdev)
    probabilities = {}
    for outcome in outcomes:
        lower = outcome - step / 2.0
        upper = outcome + step / 2.0
        probabilities[outcome] = max(distribution.cdf(upper) - distribution.cdf(lower), 0.0)
    return probabilities


def poisson_probabilities(outcomes: list[float], *, mean: float) -> dict[float, float]:
    """Calculate Poisson probabilities for an integer outcome grid."""

    if mean <= 0:
        raise ValueError("mean must be greater than zero.")
    probabilities = {}
    for outcome in outcomes:
        if not _is_integer_outcome(outcome) or outcome < 0:
            probabilities[outcome] = 0.0
            continue
        k = int(round(outcome))
        probabilities[outcome] = exp(k * log(mean) - mean - lgamma(k + 1))
    return probabilities


def negative_binomial_probabilities(
    outcomes: list[float],
    *,
    mean: float,
    dispersion: float,
) -> dict[float, float]:
    """Calculate negative-binomial probabilities with variance above the mean."""

    if mean <= 0:
        raise ValueError("mean must be greater than zero.")
    if dispersion <= 0:
        raise ValueError("dispersion must be greater than zero.")

    variance = mean + dispersion * mean * mean
    r = mean * mean / (variance - mean)
    p = r / (r + mean)
    probabilities = {}
    for outcome in outcomes:
        if not _is_integer_outcome(outcome) or outcome < 0:
            probabilities[outcome] = 0.0
            continue
        k = int(round(outcome))
        log_probability = (
            lgamma(k + r)
            - lgamma(r)
            - lgamma(k + 1)
            + r * log(p)
            + k * log(1.0 - p)
        )
        probabilities[outcome] = exp(log_probability)
    return probabilities


def summarize_expected_value(
    analysis: MiddleAnalysis,
    probabilities: dict[float, float],
) -> ExpectedValueSummary:
    """Summarize expected value from payoff points and outcome probabilities."""

    expected_profit = 0.0
    probability_middle = 0.0
    probability_profit = 0.0
    probability_loss = 0.0
    covered_probability = 0.0

    for point in analysis.payoff_points:
        probability = probabilities.get(point.outcome, 0.0)
        expected_profit += probability * point.total_profit
        covered_probability += probability
        if point.state == "middle":
            probability_middle += probability
        if point.total_profit > 0:
            probability_profit += probability
        elif point.total_profit < 0:
            probability_loss += probability

    return ExpectedValueSummary(
        expected_profit=expected_profit,
        expected_return_on_stake=expected_profit / analysis.total_stake,
        probability_middle=probability_middle,
        probability_profit=probability_profit,
        probability_loss=probability_loss,
        covered_probability=covered_probability,
    )


def _leg_result(leg: BetLeg, outcome: float) -> str:
    if leg.side == BetSide.OVER:
        if outcome > leg.line:
            return "win"
        if outcome < leg.line:
            return "loss"
        return "push"
    if outcome < leg.line:
        return "win"
    if outcome > leg.line:
        return "loss"
    return "push"


def _classify_outcome(outcome: float, *, over_leg: BetLeg, under_leg: BetLeg) -> str:
    over_result = _leg_result(over_leg, outcome)
    under_result = _leg_result(under_leg, outcome)
    if over_result == "win" and under_result == "win":
        return "middle"
    if "push" in {over_result, under_result}:
        return "push"
    if over_result == "loss" and under_result == "win":
        return "lower tail"
    if over_result == "win" and under_result == "loss":
        return "upper tail"
    return "dead zone"


def _validate_leg(leg: BetLeg, expected_side: BetSide | None = None) -> None:
    if expected_side is not None and leg.side != expected_side:
        raise ValueError(f"leg side must be {expected_side.value}.")
    if leg.line < 0:
        raise ValueError("line cannot be negative.")
    _validate_decimal_odds(leg.odds_decimal)
    if leg.stake < 0:
        raise ValueError("stake cannot be negative.")


def _validate_decimal_odds(odds: float) -> None:
    if odds <= 1.0:
        raise ValueError("decimal odds must be greater than 1.0.")


def _is_integer_outcome(value: float) -> bool:
    return abs(value - round(value)) < 1e-9
