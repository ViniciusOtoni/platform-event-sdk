import json

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import sessionmaker

from edp_events import OutboxRelay, add_to_outbox, new_event, register_outbox
from edp_events.publishers import InMemoryPublisher


@pytest.fixture
def db():
    metadata = MetaData()
    pedidos = Table("pedido", metadata, Column("pedido_id", String, primary_key=True))
    outbox = register_outbox(metadata)
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    return engine, sessionmaker(engine), pedidos, outbox


def _event(pedido_id, version=1):
    return new_event(type="pedidos.pedido.criado.v1", source="/x", aggregate="pedido",
                     aggregate_id=pedido_id, aggregate_version=version, data={"pedido_id": pedido_id})


def test_register_outbox_is_idempotent():
    metadata = MetaData()
    assert register_outbox(metadata) is register_outbox(metadata)


def test_event_is_written_in_the_same_transaction(db):
    _, Session, pedidos, outbox = db
    with Session() as session, session.begin():
        session.execute(pedidos.insert().values(pedido_id="p-1"))
        add_to_outbox(session, outbox, _event("p-1"))

    with Session() as session:
        assert session.execute(select(outbox.c.event_hub, outbox.c.aggregate_id)).one() == ("pedidos.pedido.v1", "p-1")


def test_rollback_discards_business_row_and_event(db):
    _, Session, pedidos, outbox = db
    with pytest.raises(RuntimeError), Session() as session, session.begin():
        session.execute(pedidos.insert().values(pedido_id="p-1"))
        add_to_outbox(session, outbox, _event("p-1"))
        raise RuntimeError("falha de negócio")

    with Session() as session:
        assert session.execute(select(outbox)).all() == []
        assert session.execute(select(pedidos)).all() == []


def test_relay_publishes_in_order_and_marks_published(db):
    _, Session, _, outbox = db
    with Session() as session, session.begin():
        add_to_outbox(session, outbox, _event("p-1", 1))
        add_to_outbox(session, outbox, _event("p-2", 1))

    publisher = InMemoryPublisher()
    relay = OutboxRelay(Session, outbox, publisher)
    assert relay.run_once() == 2
    assert [m.partition_key for m in publisher.messages] == ["p-1", "p-2"]
    assert json.loads(publisher.messages[0].body)["type"] == "pedidos.pedido.criado.v1"
    assert relay.run_once() == 0  # nada pendente

    with Session() as session:
        assert all(r.published_at is not None for r in session.execute(select(outbox)).all())


def test_relay_keeps_failed_event_pending_and_stops_batch(db):
    _, Session, _, outbox = db
    with Session() as session, session.begin():
        add_to_outbox(session, outbox, _event("p-1"))
        add_to_outbox(session, outbox, _event("p-2"))

    publisher = InMemoryPublisher(fail_on={"p-1"})
    relay = OutboxRelay(Session, outbox, publisher)
    assert relay.run_once() == 0
    assert publisher.messages == []

    with Session() as session:
        row = session.execute(select(outbox).where(outbox.c.aggregate_id == "p-1")).one()
        assert row.published_at is None and row.attempts == 1 and "falha simulada" in row.last_error

    publisher.fail_on.clear()
    assert relay.run_once() == 2
