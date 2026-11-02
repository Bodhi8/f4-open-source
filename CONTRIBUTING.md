# Contributing

Use Python 3.11 or later. Create a virtual environment, install with
`python -m pip install '.[dev]'`, then run:

```bash
python -m unittest discover -s tests -v
ruff check .
python scripts/check_public_release.py
python -m build
```

Keep runtime dependencies optional unless essential. Tests should demonstrate
invariants and edge cases, especially knowledge time, delayed outcomes and exact
decision equations. Example data must be synthetic and labeled as such. Do not
submit client data, identifiers, credentials or commercial source.

Maintain schema compatibility within the major contract version. Changing ID,
time or amount semantics requires a migration plan and a new schema version.
Use explicit UTC timestamps and deterministic seeds in reproducible examples.
