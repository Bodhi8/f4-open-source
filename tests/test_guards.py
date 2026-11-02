"""Guards for knowledge time, schema drift, the published economics example and the CLI."""

import contextlib
import dataclasses
import io
import json
import tomllib
import unittest
from pathlib import Path

import f4
from f4.cli import main
from f4.contracts import ENTITIES, AccountEvent, validate_portfolio
from f4.economics import Payoffs, best_action, expected_values, verification_threshold
from f4.synth import generate_portfolio

ROOT = Path(__file__).resolve().parents[1]

# Which fields reference which entity; used to check visibility at each record's knowledge time.
REFERENCES = {
    "Invoice": {"carrier_id": "Carrier", "debtor_id": "Debtor", "load_id": "Load"},
    "Outcome": {"invoice_id": "Invoice", "carrier_id": "Carrier"},
    "AccountEvent": {
        "carrier_id": "Carrier",
        "target_id": "BankAccount",
        "previous_target_id": "BankAccount",
    },
    "ContactPoint": {"carrier_id": "Carrier"},
    "DeviceSession": {"carrier_id": "Carrier"},
    "Document": {"carrier_id": "Carrier", "invoice_id": "Invoice"},
    "Payment": {
        "payer_id": "Debtor",
        "payee_id": "Carrier",
        "account_id": "BankAccount",
        "invoice_id": "Invoice",
    },
}


class KnowledgeTimeTests(unittest.TestCase):
    def test_synthetic_references_are_visible_when_used(self):
        for seed in (1, 42):
            tables = generate_portfolio(seed=seed).tables
            first_seen = {}
            for name, rows in tables.items():
                for row in rows:
                    key = (name, row.id)
                    first_seen[key] = min(first_seen.get(key, row.observed_at), row.observed_at)
            for name, fields in REFERENCES.items():
                for row in tables[name]:
                    for field, target in fields.items():
                        value = getattr(row, field)
                        if value:
                            self.assertLessEqual(
                                first_seen[(target, value)],
                                row.observed_at,
                                f"{name}/{row.id}.{field} sees {target}/{value} too early",
                            )

    def test_takeover_account_appears_at_takeover_and_is_restored(self):
        tables = generate_portfolio().tables
        events = {e.id: e for e in tables["AccountEvent"]}
        takeover, restore = events["takeover-bank"], events["takeover-restore"]
        account = next(b for b in tables["BankAccount"] if b.id == takeover.target_id)
        self.assertEqual(account.first_seen_at, takeover.occurred_at)
        self.assertFalse(account.verified)
        self.assertEqual(restore.target_id, takeover.previous_target_id)
        self.assertGreater(restore.occurred_at, takeover.occurred_at)
        paid_to = {p.account_id for p in tables["Payment"] if p.payee_id == "c4"}
        self.assertEqual(paid_to, {"b4"})

    def test_missing_previous_bank_reported(self):
        tables = generate_portfolio(carriers=12, invoices=60).tables
        event = tables["AccountEvent"][0]
        tables["AccountEvent"].append(
            dataclasses.replace(event, id="bad", previous_target_id="nowhere")
        )
        self.assertIn("AccountEvent/bad: missing previous bank target", validate_portfolio(tables))
        self.assertIsInstance(event, AccountEvent)


class SchemaDriftTests(unittest.TestCase):
    def test_json_schema_matches_python_records(self):
        schema = json.loads((ROOT / "schemas" / "contract-v1.json").read_text(encoding="utf-8"))
        definitions = schema["$defs"]
        self.assertEqual(set(definitions), set(ENTITIES))
        for name, cls in ENTITIES.items():
            fields = dataclasses.fields(cls)
            required = {
                f.name
                for f in fields
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
            }
            self.assertEqual(set(definitions[name]["properties"]), {f.name for f in fields}, name)
            self.assertEqual(set(definitions[name]["required"]), required, name)
            self.assertFalse(definitions[name]["additionalProperties"], name)

    def test_version_matches_project_metadata(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(f4.__version__, project["project"]["version"])


class PublishedExampleTests(unittest.TestCase):
    """The worked example in the F4 article: 3% fee, $25 call, 90% catch, $50 decline cost."""

    def payoffs(self, amount):
        return Payoffs.from_invoice(amount, 0.03, catch_rate=0.9, review_cost=25, decline_cost=50)

    def test_fee_and_exposure(self):
        payoff = self.payoffs(2500)
        self.assertAlmostEqual(payoff.fee, 75)
        self.assertAlmostEqual(payoff.loss, 2425)

    def test_threshold_scales_with_dollars_at_risk(self):
        self.assertAlmostEqual(verification_threshold(self.payoffs(2500)), 0.011455, places=5)
        self.assertAlmostEqual(verification_threshold(self.payoffs(10000)), 0.002864, places=5)

    def test_same_score_different_answer(self):
        self.assertEqual(best_action(0.005, self.payoffs(2500)), "fund")
        self.assertEqual(best_action(0.005, self.payoffs(10000)), "verify")

    def test_decline_only_above_about_27_percent(self):
        self.assertEqual(best_action(0.27, self.payoffs(2500)), "verify")
        self.assertEqual(best_action(0.28, self.payoffs(2500)), "decline")

    def test_ties_resolve_in_documented_order(self):
        payoff = Payoffs(100, 1000, 0.8, 10, 50)
        p = verification_threshold(payoff)
        values = expected_values(p, payoff)
        self.assertAlmostEqual(values["fund"], values["verify"])
        self.assertEqual(best_action(0, Payoffs(0, 0, 0, 0, 0)), "fund")

    def test_invalid_invoice_inputs(self):
        for amount, rate in ((-1, 0.03), (100, 1.5), (100, -0.1)):
            with self.assertRaises(ValueError):
                Payoffs.from_invoice(amount, rate, catch_rate=0.9, review_cost=1, decline_cost=1)


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(list(argv))
        return out.getvalue()

    def run_error(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            main(list(argv))
        self.assertEqual(raised.exception.code, 2)
        return err.getvalue()

    def test_readme_calculation(self):
        result = json.loads(
            self.run_cli(
                "calculate",
                "--probability",
                "0.10",
                "--fee",
                "100",
                "--loss",
                "1000",
                "--catch-rate",
                "0.8",
                "--review-cost",
                "10",
                "--decline-cost",
                "50",
            )
        )
        self.assertEqual(result["expected_values"], {"fund": -10, "verify": 60, "decline": -45})
        self.assertEqual(result["best_action"], "verify")
        self.assertAlmostEqual(result["verify_break_even_probability"], 0.0125)

    def test_invoice_mode(self):
        common = (
            "--probability",
            "0.005",
            "--fee-rate",
            "0.03",
            "--catch-rate",
            "0.9",
            "--review-cost",
            "25",
            "--decline-cost",
            "50",
        )
        small = json.loads(self.run_cli("calculate", "--amount", "2500", *common))
        large = json.loads(self.run_cli("calculate", "--amount", "10000", *common))
        self.assertEqual((small["best_action"], large["best_action"]), ("fund", "verify"))

    def test_no_catch_benefit_is_valid_json(self):
        result = json.loads(self.run_cli("calculate", "--catch-rate", "0"))
        self.assertIsNone(result["verify_break_even_probability"])

    def test_input_errors_are_clean(self):
        self.assertIn("probability must be <= 1", self.run_error("calculate", "--probability", "2"))
        self.assertIn("--fee-rate", self.run_error("calculate", "--amount", "100"))
        self.assertIn("either", self.run_error("calculate", "--amount", "1", "--fee", "1"))
        self.assertIn(
            "at least 12 carriers", self.run_error("synth", "--output", "x", "--carriers", "2")
        )


if __name__ == "__main__":
    unittest.main()
