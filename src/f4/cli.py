import argparse
import json

from .economics import Payoffs, expected_values
from .synth import generate_portfolio


def main() -> None:
    parser = argparse.ArgumentParser(description="F4 synthetic data and reference economics")
    commands = parser.add_subparsers(dest="command", required=True)
    synth = commands.add_parser("synth", help="generate a clearly labeled synthetic portfolio")
    synth.add_argument("--output", required=True)
    synth.add_argument("--carriers", type=int, default=24)
    synth.add_argument("--invoices", type=int, default=600)
    synth.add_argument("--seed", type=int, default=42)
    calc = commands.add_parser("calculate", help="expected dollars under supplied assumptions")
    for name, default in (
        ("probability", 0.1),
        ("fee", 100),
        ("loss", 4500),
        ("catch-rate", 0.8),
        ("review-cost", 20),
        ("decline-cost", 100),
    ):
        calc.add_argument("--" + name, type=float, default=default)
    args = parser.parse_args()
    if args.command == "synth":
        portfolio = generate_portfolio(
            carriers=args.carriers, invoices=args.invoices, seed=args.seed
        )
        portfolio.write(args.output)
        print(json.dumps({"synthetic": True, "output": args.output, "invoices": args.invoices}))
    else:
        values = expected_values(
            args.probability,
            Payoffs(args.fee, args.loss, args.catch_rate, args.review_cost, args.decline_cost),
        )
        print(
            json.dumps(
                {"expected_values": values, "best_action": max(values, key=values.get)}, indent=2
            )
        )


if __name__ == "__main__":
    main()
