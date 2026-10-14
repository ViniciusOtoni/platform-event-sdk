import json

import pytest

from edp_events import SchemaValidationError, SchemaValidator, new_event

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["pedido_id", "valor_total"],
    "properties": {
        "pedido_id": {"type": "string"},
        "valor_total": {"type": "number", "exclusiveMinimum": 0},
    },
}


def _event(data, type_="pedidos.pedido.criado.v1"):
    return new_event(type=type_, source="/x", aggregate="pedido", aggregate_id="p-1",
                     aggregate_version=1, data=data)


def test_valid_event_passes():
    SchemaValidator({"pedidos.pedido.criado.v1": SCHEMA}).validate(_event({"pedido_id": "p-1", "valor_total": 10}))


def test_invalid_event_lists_errors():
    validator = SchemaValidator({"pedidos.pedido.criado.v1": SCHEMA})
    with pytest.raises(SchemaValidationError) as exc:
        validator.validate(_event({"valor_total": -1}))
    assert any("pedido_id" in e for e in exc.value.errors)
    assert any("valor_total" in e for e in exc.value.errors)


def test_event_without_schema_is_rejected():
    validator = SchemaValidator({"pedidos.pedido.criado.v1": SCHEMA})
    with pytest.raises(SchemaValidationError, match="Published Language"):
        validator.validate(_event({}, type_="pedidos.pedido.cancelado.v1"))


def test_from_directory(tmp_path):
    (tmp_path / "pedidos.pedido.criado.v1.schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    assert SchemaValidator.from_directory(tmp_path).event_types == {"pedidos.pedido.criado.v1"}
