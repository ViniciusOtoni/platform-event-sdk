"""Validação do payload (``data``) por JSON Schema draft 2020-12 (ADR-0003).

Os schemas são gerados a partir do contrato ODCS do domínio (ADR-0005) e versionados no repositório
do serviço, um arquivo por tipo de evento: ``<tipo>.schema.json``. O produtor valida ANTES de gravar
na outbox, então um evento fora do contrato nunca sai do serviço.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from edp_events.envelope import CloudEvent


class SchemaValidationError(ValueError):
    def __init__(self, event_type: str, errors: list[str]):
        self.event_type = event_type
        self.errors = errors
        super().__init__(f"Evento {event_type} viola o contrato: " + "; ".join(errors))


class SchemaValidator:
    def __init__(self, schemas: dict[str, dict[str, Any]]):
        self._validators = {}
        for event_type, schema in schemas.items():
            Draft202012Validator.check_schema(schema)
            self._validators[event_type] = Draft202012Validator(schema)

    @classmethod
    def from_directory(cls, path: str | Path) -> SchemaValidator:
        schemas = {}
        for file in sorted(Path(path).glob("*.schema.json")):
            schemas[file.name.removesuffix(".schema.json")] = json.loads(file.read_text(encoding="utf-8"))
        if not schemas:
            raise FileNotFoundError(f"Nenhum *.schema.json em {path}")
        return cls(schemas)

    @property
    def event_types(self) -> set[str]:
        return set(self._validators)

    def validate(self, event: CloudEvent) -> None:
        validator = self._validators.get(event.type)
        if validator is None:
            raise SchemaValidationError(event.type, ["tipo sem schema registrado (fora da Published Language)"])
        errors = sorted(
            f"{'/'.join(map(str, e.absolute_path)) or '<raiz>'}: {e.message}"
            for e in validator.iter_errors(event.data)
        )
        if errors:
            raise SchemaValidationError(event.type, errors)
