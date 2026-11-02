import importlib.util
import unittest

from f4.adapters import DuckDBAdapter
from f4.synth import generate_portfolio


@unittest.skipUnless(importlib.util.find_spec("duckdb"), "install the duckdb extra")
class DuckDBTests(unittest.TestCase):
    def test_json_body_roundtrip(self):
        import duckdb

        rows = generate_portfolio(carriers=12, invoices=60).tables["Invoice"]
        with duckdb.connect(":memory:") as connection:
            adapter = DuckDBAdapter(connection)
            adapter.write("invoices", rows)
            self.assertEqual(adapter.read_bodies("Invoice", "invoices"), rows)

    def test_typed_table_read(self):
        import duckdb

        with duckdb.connect(":memory:") as connection:
            connection.execute(
                "CREATE TABLE debtors (id VARCHAR, name VARCHAR, observed_at TIMESTAMPTZ)"
            )
            connection.execute(
                "INSERT INTO debtors VALUES (?, ?, ?)", ["d", "Synthetic", "2025-01-01T00:00:00Z"]
            )
            self.assertEqual(
                DuckDBAdapter(connection).read("Debtor", "debtors")[0].name, "Synthetic"
            )
