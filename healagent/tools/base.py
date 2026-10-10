"""Shared helpers for schema-validated deterministic tools."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from healagent.core.types import ToolResult
from healagent.data.generator import EcommerceWorld, default_world

InputT = TypeVar("InputT", bound=BaseModel)


class SchemaTool(Generic[InputT]):
    """Base class for tools with a Pydantic input schema."""

    name: str
    input_model: type[InputT]
    latency_ms: float = 10.0

    def __init__(self, world: EcommerceWorld | None = None) -> None:
        self.world = world or default_world()

    def call(self, args: dict) -> ToolResult:
        try:
            validated = self.input_model.model_validate(args)
        except ValidationError as exc:
            message = exc.errors()[0]["msg"] if exc.errors() else "invalid arguments"
            return ToolResult(
                ok=False,
                error=f"schema_error: {message}",
                latency_ms=self.latency_ms,
            )

        try:
            output = self.run(validated)
        except KeyError as exc:
            return ToolResult(
                ok=False,
                error=f"not_found: {exc.args[0]}",
                latency_ms=self.latency_ms,
            )
        except ValueError as exc:
            return ToolResult(
                ok=False,
                error=f"invalid_request: {exc}",
                latency_ms=self.latency_ms,
            )

        return ToolResult(ok=True, output=output, latency_ms=self.latency_ms)

    def run(self, args: InputT) -> dict:
        raise NotImplementedError
