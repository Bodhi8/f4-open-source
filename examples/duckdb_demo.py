"""Optional local DuckDB round trip; install the duckdb extra first."""

import duckdb
from f4.adapters import DuckDBAdapter
from f4.synth import generate_portfolio

portfolio = generate_portfolio()
with duckdb.connect(":memory:") as connection:
    adapter = DuckDBAdapter(connection)
    adapter.write("invoices", portfolio.tables["Invoice"])
    assert adapter.read_bodies("Invoice", "invoices") == portfolio.tables["Invoice"]
    print(
        "Synthetic invoices stored:",
        connection.execute("SELECT count(*) FROM invoices").fetchone()[0],
    )
