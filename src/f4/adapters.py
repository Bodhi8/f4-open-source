"""Local adapters. No implicit network access or warehouse credentials."""

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import Record, from_dict, to_dict


def map_records(
    entity: str, rows: Iterable[Mapping[str, Any]], mapping: Mapping[str, str]
) -> list[Record]:
    """mapping is {canonical_field: source_column}; transforms must occur upstream."""
    return [
        from_dict(entity, {target: row[source] for target, source in mapping.items()})
        for row in rows
    ]


def read_jsonl(entity: str, path: str | Path) -> list[Record]:
    with Path(path).open(encoding="utf-8") as stream:
        return [from_dict(entity, json.loads(line)) for line in stream if line.strip()]


def write_jsonl(records: Iterable[Record], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as stream:
        for row in records:
            stream.write(json.dumps(to_dict(row), sort_keys=True, allow_nan=False) + "\n")


class DuckDBAdapter:
    """Explicit client-owned connection; caller controls lifecycle and permissions."""

    def __init__(self, connection: Any):
        self.connection = connection

    @staticmethod
    def _identifier(name: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("table name must be a simple SQL identifier")
        return '"' + name + '"'

    def read(self, entity: str, table: str) -> list[Record]:
        cursor = self.connection.execute(f"SELECT * FROM {self._identifier(table)}")
        names = [field[0] for field in cursor.description]
        return [from_dict(entity, dict(zip(names, row))) for row in cursor.fetchall()]

    def write(self, table: str, records: Iterable[Record]) -> None:
        """Store JSON bodies losslessly; use explicit views for typed analytical columns."""
        name = self._identifier(table)
        self.connection.execute(f"CREATE TABLE IF NOT EXISTS {name} (body JSON)")
        values = [(json.dumps(to_dict(row), allow_nan=False),) for row in records]
        if values:
            self.connection.executemany(f"INSERT INTO {name} VALUES (?)", values)

    def read_bodies(self, entity: str, table: str) -> list[Record]:
        return [
            from_dict(entity, json.loads(row[0]))
            for row in self.connection.execute(
                f"SELECT body FROM {self._identifier(table)}"
            ).fetchall()
        ]
