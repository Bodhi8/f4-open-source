"""Run after installing vector1-f4-core. All data are synthetic."""

from f4 import Payoffs, expected_values, generate_portfolio
from f4.contracts import validate_portfolio
from f4.features import basic_graph_features

portfolio = generate_portfolio(seed=42)
assert not validate_portfolio(portfolio.tables)
edges = [(r.carrier_id, r.debtor_id) for r in portfolio.tables["Invoice"]]
print("SYNTHETIC portfolio:", len(portfolio.tables["Invoice"]), "invoices")
print("Reference graph:", basic_graph_features(edges)["c0"])
print("Expected dollars:", expected_values(0.1, Payoffs(100, 1000, 0.8, 10, 50)))
