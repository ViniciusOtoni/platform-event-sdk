import json

import pytest

from edp_events import CloudEvent, EventType, event_hub_for, new_event


def test_event_type_parse_and_event_hub():
    t = EventType.parse("pedidos.pedido.criado.v1")
    assert (t.domain, t.aggregate, t.event, t.major) == ("pedidos", "pedido", "criado", 1)
    assert t.event_hub == "pedidos.pedido.v1"
    assert event_hub_for("pagamentos.pagamento.aprovado.v2") == "pagamentos.pagamento.v2"


@pytest.mark.parametrize(
    "value",
    ["Pedidos.pedido.criado.v1", "pedidos.pedido.criado", "pedidos.criado.v1", "pedidos.pedido.criado.v0"],
)
def test_event_type_invalid(value):
    with pytest.raises(ValueError):
        EventType.parse(value)


def test_event_type_rejects_crud_events():
    with pytest.raises(ValueError, match="genérico"):
        EventType.parse("pedidos.pedido.atualizado.v1")


def test_new_event_builds_cloudevent_with_platform_extensions():
    event = new_event(
        type="pedidos.pedido.criado.v1",
        source="/dominios/pedidos/pedidos-api",
        aggregate="pedido",
        aggregate_id="p-1",
        aggregate_version=1,
        data={"pedido_id": "p-1"},
        traceparent="00-abc-def-01",
    )
    body = event.to_dict()
    assert body["specversion"] == "1.0"
    assert body["subject"] == "pedido/p-1"
    assert body["aggregateid"] == "p-1"
    assert body["aggregateversion"] == 1
    assert body["dataschema"] == "urn:schema:pedidos.pedido.criado.v1"
    assert body["traceparent"] == "00-abc-def-01"
    assert event.event_hub == "pedidos.pedido.v1"


def test_roundtrip_json():
    event = new_event(
        type="pedidos.pedido.cancelado.v1", source="/x", aggregate="pedido",
        aggregate_id="p-2", aggregate_version=3, data={"motivo": "CLIENTE_DESISTIU"},
    )
    again = CloudEvent.from_dict(json.loads(event.to_json()))
    assert again == event


def test_aggregate_version_must_be_positive():
    with pytest.raises(ValueError):
        new_event(type="pedidos.pedido.criado.v1", source="/x", aggregate="pedido",
                  aggregate_id="p", aggregate_version=0, data={})
