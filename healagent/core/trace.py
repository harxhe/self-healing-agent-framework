"""JSONL trace logging: one :class:`TraceRecord` per line per step."""

from __future__ import annotations

from pathlib import Path

from .types import TraceRecord

DEFAULT_TRACE_DIR = Path("results") / "traces"


class TraceLogger:
    """Append :class:`TraceRecord` objects as JSONL to ``results/traces/<run_id>.jsonl``."""

    def __init__(self, run_id: str, trace_dir: Path | str = DEFAULT_TRACE_DIR) -> None:
        self.run_id = run_id
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.trace_dir / f"{run_id}.jsonl"

    def log(self, record: TraceRecord) -> None:
        """Serialise and append a single trace record."""
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(record.model_dump_json())
            fh.write("\n")

    def read_all(self) -> list[TraceRecord]:
        """Read back all records written for this run."""
        if not self.path.exists():
            return []
        records: list[TraceRecord] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(TraceRecord.model_validate_json(line))
        return records
