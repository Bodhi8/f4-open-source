import argparse
import json
import math

from . import __version__
from .economics import Payoffs, best_action, expected_values, verification_threshold
from .synth import generate_portfolio

DEFAULT_FEE = 100.0
DEFAULT_LOSS = 4500.0


def _payoffs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Payoffs:
    shared = dict(
        catch_rate=args.catch_rate, review_cost=args.review_cost, decline_cost=args.decline_cost
    )
    if args.amount is None:
        if args.fee_rate is not None:
            parser.error("--fee-rate requires --amount")
        fee = DEFAULT_FEE if args.fee is None else args.fee
        loss = DEFAULT_LOSS if args.loss is None else args.loss
        return Payoffs(fee=fee, loss=loss, **shared)
    if args.fee is not None or args.loss is not None:
        parser.error("use either --amount with --fee-rate, or --fee with --loss")
    if args.fee_rate is None:
        parser.error("--amount requires --fee-rate")
    return Payoffs.from_invoice(args.amount, args.fee_rate, **shared)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="f4", description="F4 synthetic data and reference economics"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    synth = commands.add_parser("synth", help="generate a clearly labeled synthetic portfolio")
    synth.add_argument("--output", required=True)
    synth.add_argument("--carriers", type=int, default=24)
    synth.add_argument("--invoices", type=int, default=600)
    synth.add_argument("--seed", type=int, default=42)
    calc = commands.add_parser(
        "calculate",
        help="expected dollars under supplied assumptions",
        description="Give --fee and --loss directly, or --amount and --fee-rate for one invoice.",
    )
    calc.add_argument("--probability", type=float, default=0.1)
    calc.add_argument("--fee", type=float, help=f"fee earned if legitimate (default {DEFAULT_FEE})")
    calc.add_argument("--loss", type=float, help=f"exposure if fraudulent (default {DEFAULT_LOSS})")
    calc.add_argument("--amount", type=float, help="invoice face value")
    calc.add_argument("--fee-rate", type=float, help="factoring fee as a fraction, e.g. 0.03")
    calc.add_argument("--catch-rate", type=float, default=0.8)
    calc.add_argument("--review-cost", type=float, default=20)
    calc.add_argument("--decline-cost", type=float, default=100)
    args = parser.parse_args(argv)
    try:
        if args.command == "synth":
            portfolio = generate_portfolio(
                carriers=args.carriers, invoices=args.invoices, seed=args.seed
            )
            portfolio.write(args.output)
            print(json.dumps({"synthetic": True, "output": args.output, "invoices": args.invoices}))
            return
        payoff = _payoffs(args, parser)
        break_even = verification_threshold(payoff)
        result = {
            "expected_values": expected_values(args.probability, payoff),
            "best_action": best_action(args.probability, payoff),
            # null when verification never pays (no catch benefit); keeps output valid JSON
            "verify_break_even_probability": None if math.isinf(break_even) else break_even,
            "assumptions": {
                "fee": payoff.fee,
                "loss": payoff.loss,
                "catch_rate": payoff.catch_rate,
                "review_cost": payoff.review_cost,
                "decline_cost": payoff.decline_cost,
            },
        }
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
