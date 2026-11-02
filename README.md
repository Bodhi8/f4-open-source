# F4 · Freight Finance Fraud Framework

[![Core tests and packages](https://github.com/Bodhi8/f4-open-source/actions/workflows/ci.yml/badge.svg)](https://github.com/Bodhi8/f4-open-source/actions/workflows/ci.yml)

**A Python foundation for freight-finance risk research, by Vector1 Research.**

F4 connects freight identities, transactions and outcomes to decisions expressed
in dollars. This public package contains the canonical data contract, a seeded
synthetic portfolio generator, reference graph features and an expected-value
calculator. It runs locally with Python 3.11 or later and has no required runtime
dependencies, hosted services or telemetry.

Version **0.1.0** is a research reference release. All examples and measurements
use synthetic data. There are no claims of validated client savings or production
fraud-detection performance.

## Quick start

From a source checkout:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
f4 synth --output demo-data --seed 42
f4 calculate --probability 0.10 --fee 100 --loss 1000 --catch-rate 0.8 --review-cost 10 --decline-cost 50
```

The calculator returns expected values of **−10 for fund, 60 for verify and −45
for decline** under those supplied assumptions, plus the verification break-even
probability. These are expected dollars per case, not observed savings.

To install directly from GitHub instead:
`python -m pip install "git+https://github.com/Bodhi8/f4-open-source"`.

### Same score, different answer

The verification threshold scales with the dollars at risk, so one score cutoff
across a book is wrong for most invoices. With a 3% fee, a $25 call that catches
90% of fraud and a $50 cost for declining a good invoice (illustrative values):

```bash
f4 calculate --probability 0.005 --amount 2500 --fee-rate 0.03 --catch-rate 0.9 --review-cost 25 --decline-cost 50
f4 calculate --probability 0.005 --amount 10000 --fee-rate 0.03 --catch-rate 0.9 --review-cost 25 --decline-cost 50
```

At the same 0.5% fraud score, the right action is **fund** for the $2,500 invoice
(verification pays above 1.15%) and **verify** for the $10,000 invoice (above
0.29%). `examples/invoice_size.py` prints both. `--amount` with `--fee-rate`
sets fee `m = f × A` and exposure `L = (1 − f) × A`; use `--fee` and `--loss`
for other advance terms.

```python
from f4 import Payoffs, best_action, expected_values, generate_portfolio
from f4.contracts import validate_portfolio

portfolio = generate_portfolio(carriers=24, invoices=600, seed=42)
assert validate_portfolio(portfolio.tables) == []

payoff = Payoffs(fee=100, loss=1000, catch_rate=0.8, review_cost=10, decline_cost=50)
print(expected_values(0.10, payoff))
print(best_action(0.10, payoff))  # verify; exact ties resolve fund, verify, decline
```

## What is included

| Module | Public implementation |
| --- | --- |
| `contracts` | Twelve typed record types; UTC timestamps; schema, amount, propensity and reference checks; keyed identifier hashing |
| `synth` | Seeded portfolios with rings, account takeovers, concentrated trade and duplicate billing, with delayed confirmations; every reference is visible at the time it is used |
| `features` | Reference degree and connected-component features |
| `economics` | Fund/verify/decline expected values, best action, per-invoice payoffs and verification break-even |
| `adapters` | JSONL, explicit source-column mapping and an optional DuckDB adapter |
| `cli` | Synthetic-data generation and a command-line decision calculator |

The separate commercial implementation contains entity resolution, the temporal
graph, full features, scheme candidates, carrier monitoring, fitted risk models,
capacity allocation, learning and governance. It is not part of this Apache-2.0
distribution.

## How the economics work

For fraud probability `p`, legitimate fee `m`, fraud exposure `L`, verification
catch rate `r`, review cost `c` and legitimate-decline opportunity cost `k`:

```text
fund    = (1 - p) * m - p * L
verify  = (1 - p) * m - p * (1 - r) * L - c
decline = -(1 - p) * k
```

The verification break-even `c / (r * L)` compares verification with funding.
Decline can still be preferable. Fees, exposure, review effectiveness and
opportunity cost are explicit assumptions that must be estimated for the client.
All amounts in a calculation must use the same currency. Expected values retain
floating-point precision for research; this package is not a money-movement or
ledger system.

## Data and time

Every canonical record carries `observed_at`, the time the client first knew the
record or revision. Event dates and knowledge dates are different. Revisions are
append-only observations with the same ID and a later `observed_at`.

Synthetic truth is stored separately from input records. An invoice does not
contain its fraud label. Outcomes arrive later, allowing leakage and delayed-label
tests to replay realistic knowledge boundaries.

Identifiers can be normalized and HMAC-hashed inside the client's environment.
Keys are supplied by the client, never embedded in the framework. The synthetic
generator uses a clearly synthetic deterministic key for reproducible fake data.

## Examples and tests

```bash
python examples/quickstart.py
python examples/invoice_size.py
python -m unittest discover -s tests -v
```

Open `examples/public_demo.ipynb` for a notebook version. The optional DuckDB
example requires `python -m pip install '.[duckdb]'`.

- [Data contract](docs/DATA_CONTRACT.md)
- [Architecture and open-core boundary](docs/ARCHITECTURE.md)
- [Development](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Release notes](CHANGELOG.md)

## Commercial licensing and pilots

The commercial F4 distribution installs inside a client's own cloud account and
adds the modules listed above. For licensing, a diagnostic or a pilot on your
own history, contact Vector1 Research at [vector1.ai](https://vector1.ai)
(brian at vector1.ai).

## Citation

If you use F4 in research, cite it with the metadata in [CITATION.cff](CITATION.cff).

## License

Apache License 2.0. Copyright 2026 Vector1 Research LLC. See [LICENSE](LICENSE)
and [NOTICE](NOTICE). The F4 and Vector1 names are not licensed as trademarks.
