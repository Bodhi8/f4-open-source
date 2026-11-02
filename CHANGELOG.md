# Changelog

## Unreleased

- Fixed synthetic knowledge-time leaks: bank accounts were observed before the carriers
  that used them, and the takeover account was visible 240 days before the takeover.
  Accounts now appear when first used. Invoices, outcomes and truth labels are unchanged.
- Added a restore event after the synthetic account takeover, so later payments agree with
  the account history (26 account events instead of 25).
- `validate_portfolio` now checks `previous_target_id` on bank changes.
- Added `Payoffs.from_invoice`, `best_action` and `examples/invoice_size.py`, reproducing
  the published fund-versus-verify example for $2,500 and $10,000 invoices.
- CLI: `--amount` with `--fee-rate`, verification break-even in the output, `--version`,
  and clean error messages instead of tracebacks.
- Tests for knowledge-time visibility, JSON Schema drift, version consistency, the
  published example and the CLI. CI now covers Python 3.14 and current action versions.

## 0.1.0 · 2026-11-01

- Added twelve canonical record types, as-of revision selection and portfolio validation.
- Added seeded synthetic portfolios with four injected fraud schemes and delayed outcomes.
- Added reference graph features, HMAC identifier handling and expected-value economics.
- Added CLI, JSONL and optional DuckDB adapters, notebook, tests and GitHub CI.
- Initial research release; no production performance claims.
