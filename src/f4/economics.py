"""Reference expected-dollar calculator from the F4 product specification."""

from dataclasses import dataclass
from math import inf

from .contracts import finite, probability


@dataclass(frozen=True)
class Payoffs:
    fee: float
    loss: float
    catch_rate: float
    review_cost: float
    decline_cost: float

    def __post_init__(self) -> None:
        for name in ("fee", "loss", "review_cost", "decline_cost"):
            finite(getattr(self, name), name, 0)
        probability(self.catch_rate, "catch_rate")


def expected_values(p: float, payoff: Payoffs) -> dict[str, float]:
    probability(p)
    return {
        "fund": (1 - p) * payoff.fee - p * payoff.loss,
        "verify": (1 - p) * payoff.fee
        - p * (1 - payoff.catch_rate) * payoff.loss
        - payoff.review_cost,
        "decline": -(1 - p) * payoff.decline_cost,
    }


def verification_threshold(payoff: Payoffs) -> float:
    """Break-even versus funding, not versus decline. inf means no catch benefit."""
    benefit = payoff.catch_rate * payoff.loss
    return payoff.review_cost / benefit if benefit else inf
