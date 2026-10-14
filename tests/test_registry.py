import json
from types import SimpleNamespace

from azure.schemaregistry import SchemaFormat

from edp_events.registry import load_schemas, register_schemas


class FakeClient:
    def __init__(self):
        self.calls = []

    def register_schema(self, group, name, definition, fmt):
        self.calls.append((group, name, json.loads(definition), fmt))
        return SimpleNamespace(id=f"id-{name}")


def test_registers_each_schema_as_json_named_by_event_type(tmp_path):
    (tmp_path / "pedidos.pedido.criado.v1.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    (tmp_path / "pedidos.pedido.cancelado.v1.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    (tmp_path / "LEIAME.md").write_text("ignorado", encoding="utf-8")

    client = FakeClient()
    ids = register_schemas(tmp_path, "ns.servicebus.windows.net", "pedidos", client=client)

    assert ids == {
        "pedidos.pedido.cancelado.v1": "id-pedidos.pedido.cancelado.v1",
        "pedidos.pedido.criado.v1": "id-pedidos.pedido.criado.v1",
    }
    assert {(g, n, f) for g, n, _, f in client.calls} == {
        ("pedidos", "pedidos.pedido.criado.v1", SchemaFormat.JSON),
        ("pedidos", "pedidos.pedido.cancelado.v1", SchemaFormat.JSON),
    }


def test_canonical_definition_is_stable(tmp_path):
    (tmp_path / "a.b.c.v1.schema.json").write_text('{\n  "type": "object",\n  "x": "ç"\n}', encoding="utf-8")
    assert load_schemas(tmp_path) == {"a.b.c.v1": '{"type":"object","x":"ç"}'}
