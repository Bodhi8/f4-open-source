"""Reference expected-dollar calculator from the F4 product specification."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf

from .contracts import finite, probability

ACTIONS = ("fund", "verify", "decline")


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

    @classmethod
    def from_invoice(
        cls,
        amount: float,
        fee_rate: float,
        *,
        catch_rate: float,
        review_cost: float,
        decline_cost: float,
    ) -> Payoffs:
        """Payoffs for one invoice: fee m = f * A and fraud exposure L = (1 - f) * A.

        Exposure assumes the factor advances the face value net of its fee and
        recovers nothing. Supply ``Payoffs`` directly for other advance terms.
        """
        finite(amount, "amount", 0)
        probability(fee_rate, "fee_rate")
        return cls(
            fee=fee_rate * amount,
            loss=(1 - fee_rate) * amount,
            catch_rate=catch_rate,
            review_cost=review_cost,
            decline_cost=decline_cost,
        )


def expected_values(p: float, payoff: Payoffs) -> dict[str, float]:
    probability(p)
    return {
        "fund": (1 - p) * payoff.fee - p * payoff.loss,
        "verify": (1 - p) * payoff.fee
        - p * (1 - payoff.catch_rate) * payoff.loss
        - payoff.review_cost,
        "decline": -(1 - p) * payoff.decline_cost,
    }


def best_action(p: float, payoff: Payoffs) -> str:
    """Highest expected value; exact ties resolve in the order fund, verify, decline."""
    values = expected_values(p, payoff)
    return max(ACTIONS, key=lambda action: values[action])


def verification_threshold(payoff: Payoffs) -> float:
    """Break-even versus funding, not versus decline. inf means no catch benefit."""
    benefit = payoff.catch_rate * payoff.loss
    return payoff.review_cost / benefit if benefit else inf
