"""Same fraud score, different answer: the verification threshold scales with dollars at risk.

Illustrative assumptions only: 3% factoring fee, $25 verification call, 90% of fraud caught
by the call, $50 relationship cost for declining a good invoice. Not client data.
"""

from f4 import Payoffs, best_action, verification_threshold

SCORE = 0.005  # the model's fraud probability for both invoices

for amount in (2_500, 10_000):
    payoff = Payoffs.from_invoice(amount, 0.03, catch_rate=0.9, review_cost=25, decline_cost=50)
    print(
        f"${amount:>6,} invoice: verify pays above {verification_threshold(payoff):.2%}; "
        f"at a {SCORE:.1%} score -> {best_action(SCORE, payoff)}"
    )
