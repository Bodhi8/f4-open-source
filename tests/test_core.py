import json
import math
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from f4.adapters import DuckDBAdapter, map_records, read_jsonl, write_jsonl
from f4.contracts import (
    Carrier,
    Decision,
    Invoice,
    Outcome,
    from_dict,
    hash_identifier,
    latest_as_of,
    timestamp,
    to_dict,
    validate_portfolio,
)
from f4.economics import Payoffs, expected_values, verification_threshold
from f4.features import basic_graph_features
from f4.synth import Portfolio, generate_portfolio

AT = datetime(2025, 1, 1, tzinfo=timezone.utc)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.carrier = Carrier(id="c", legal_name="Demo", onboarded_at=AT, observed_at=AT)

    def test_timezone_required_and_normalized(self):
        with self.assertRaises(ValueError):
            timestamp("2025-01-01T00:00:00")
        self.assertEqual(timestamp("2025-01-01T01:00:00+01:00"), AT)

    def test_roundtrip_all_twelve_entities(self):
        data = generate_portfolio(carriers=12, invoices=60)
        data.tables["Decision"] = [
            Decision(
                id="d",
                invoice_id="i0",
                action="verify",
                fraud_probability=0.2,
                propensity=0.1,
                action_probabilities={"fund": 0.9, "verify": 0.1, "decline": 0},
                expected_values={"fund": 1, "verify": 2, "decline": -1},
                reason_codes=("TEST",),
                model_version="m",
                policy_version="p",
                decided_at=AT,
                observed_at=AT,
            )
        ]
        for entity, rows in data.tables.items():
            self.assertTrue(rows, entity)
            for row in rows:
                self.assertEqual(from_dict(entity, json.loads(json.dumps(to_dict(row)))), row)

    def test_rejects_unknown_schema_and_fields(self):
        with self.assertRaises(ValueError):
            replace(self.carrier, schema_version="2")
        with self.assertRaises(TypeError):
            from_dict("Carrier", {**to_dict(self.carrier), "surprise": 1})

    def test_missing_ids_and_name(self):
        for kw in ({"id": ""}, {"legal_name": " "}):
            with self.assertRaises(ValueError):
                replace(self.carrier, **kw)

    def test_point_in_time_version_selection(self):
        newer = replace(self.carrier, legal_name="New", observed_at=AT + timedelta(days=1))
        self.assertEqual(latest_as_of([newer, self.carrier], AT), [self.carrier])
        self.assertEqual(latest_as_of([newer, self.carrier], newer.observed_at), [newer])

    def test_ambiguous_versions_rejected(self):
        with self.assertRaises(ValueError):
            latest_as_of([self.carrier, self.carrier], AT)

    def test_invoice_constraints(self):
        args = dict(
            id="i",
            carrier_id="c",
            debtor_id="d",
            load_id="l",
            amount=100,
            advance=90,
            submitted_at=AT,
            due_at=AT,
            observed_at=AT,
        )
        for kw in (
            {"advance": 101},
            {"amount": float("nan")},
            {"amount": -1},
            {"due_at": AT - timedelta(days=1)},
            {"currency": "usd"},
        ):
            with self.assertRaises(ValueError):
                Invoice(**(args | kw))

    def test_outcome_cannot_have_negative_net_loss(self):
        with self.assertRaises(ValueError):
            Outcome(
                id="o",
                invoice_id="i",
                carrier_id="c",
                is_fraud=True,
                confirmed_at=AT,
                observed_at=AT,
                loss=10,
                recovery=20,
            )

    def test_hmac_is_domain_and_key_separated(self):
        a = hash_identifier("001", secret=b"x" * 32, namespace="bank")
        self.assertNotEqual(a, hash_identifier("1", secret=b"x" * 32, namespace="bank"))
        self.assertNotEqual(a, hash_identifier("001", secret=b"y" * 32, namespace="bank"))
        self.assertNotEqual(a, hash_identifier("001", secret=b"x" * 32, namespace="phone"))
        with self.assertRaises(ValueError):
            hash_identifier("001", secret=b"short", namespace="bank")

    def test_dangling_references_reported(self):
        portfolio = generate_portfolio(carriers=12, invoices=60)
        portfolio.tables["Debtor"] = []
        self.assertTrue(any("missing Debtor" in e for e in validate_portfolio(portfolio.tables)))

    def test_duplicate_versions_reported(self):
        self.assertTrue(validate_portfolio({"Carrier": [self.carrier, self.carrier]}))


class EconomicsTests(unittest.TestCase):
    def test_spec_equations(self):
        ev = expected_values(0.1, Payoffs(100, 1000, 0.8, 10, 50))
        self.assertAlmostEqual(ev["fund"], -10)
        self.assertAlmostEqual(ev["verify"], 60)
        self.assertAlmostEqual(ev["decline"], -45)

    def test_threshold_equality(self):
        payoff = Payoffs(100, 1000, 0.8, 10, 50)
        p = verification_threshold(payoff)
        ev = expected_values(p, payoff)
        self.assertAlmostEqual(ev["fund"], ev["verify"])

    def test_no_catch_no_break_even(self):
        self.assertEqual(verification_threshold(Payoffs(1, 100, 0, 1, 1)), math.inf)

    def test_probability_boundaries(self):
        payoff = Payoffs(100, 1000, 1, 10, 50)
        self.assertEqual(expected_values(0, payoff)["fund"], 100)
        self.assertEqual(expected_values(1, payoff)["decline"], 0)
        for p in (-1, 1.1, float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                expected_values(p, payoff)

    def test_invalid_payoffs(self):
        with self.assertRaises(ValueError):
            Payoffs(100, -1, 0.8, 10, 50)


class DataTests(unittest.TestCase):
    def test_reproducible_and_different_seed(self):
        a = generate_portfolio(carriers=12, invoices=60, seed=1)
        b = generate_portfolio(carriers=12, invoices=60, seed=1)
        c = generate_portfolio(carriers=12, invoices=60, seed=2)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_schemes_and_delayed_labels(self):
        data = generate_portfolio()
        self.assertEqual(
            set(data.truth.values()), {"clean", "ring", "takeover", "collusion", "double_billing"}
        )
        invoices = {r.id: r for r in data.tables["Invoice"]}
        self.assertTrue(
            all(o.observed_at > invoices[o.invoice_id].observed_at for o in data.tables["Outcome"])
        )
        self.assertEqual(validate_portfolio(data.tables), [])

    def test_synthetic_truth_is_separate(self):
        data = generate_portfolio(carriers=12, invoices=60)
        for row in data.tables["Invoice"]:
            self.assertNotIn("scheme", to_dict(row))

    def test_portfolio_disk_roundtrip(self):
        data = generate_portfolio(carriers=12, invoices=60)
        with tempfile.TemporaryDirectory() as directory:
            data.write(directory)
            self.assertEqual(Portfolio.read(directory), data)

    def test_jsonl_and_mapping(self):
        c = Carrier(id="c", legal_name="Demo", onboarded_at=AT, observed_at=AT)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "rows.jsonl"
            write_jsonl([c], path)
            self.assertEqual(read_jsonl("Carrier", path), [c])
        self.assertEqual(map_records("Carrier", [to_dict(c)], {k: k for k in to_dict(c)}), [c])

    def test_sql_identifier_restrictions(self):
        with self.assertRaises(ValueError):
            DuckDBAdapter._identifier("rows; DROP TABLE rows")

    def test_basic_graph_components(self):
        f = basic_graph_features([("a", "b"), ("b", "c"), ("a", "b"), ("d", "e")])
        self.assertEqual(f["a"], {"degree": 1, "component_size": 3})
        self.assertEqual(f["d"]["component_size"], 2)

    def test_small_synthetic_input_rejected(self):
        with self.assertRaises(ValueError):
            generate_portfolio(carriers=2, invoices=10)


if __name__ == "__main__":
    unittest.main()
