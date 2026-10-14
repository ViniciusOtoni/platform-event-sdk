"""Transactional Outbox (ADR-0002).

1. ``register_outbox(metadata)`` declara a tabela ``outbox`` no metadata do serviço (Alembic a enxerga).
2. ``add_to_outbox(session, event)`` grava o evento NA MESMA transação do agregado.
3. ``OutboxRelay`` lê pendentes com ``FOR UPDATE SKIP LOCKED`` (várias réplicas sem duplicar trabalho),
   publica e marca ``published_at``. Falha entre publicar e marcar => republica (at-least-once);
   os consumidores deduplicam por ``id`` do evento.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, Text, select, update
from sqlalchemy.orm import Session

from edp_events.envelope import CloudEvent
from edp_events.schema import SchemaValidator

log = logging.getLogger(__name__)

OUTBOX_TABLE = "outbox"


def register_outbox(metadata: MetaData) -> Table:
    """Declara (ou devolve, se já declarada) a tabela ``outbox`` no metadata do serviço."""
    if OUTBOX_TABLE in metadata.tables:
        return metadata.tables[OUTBOX_TABLE]
    return Table(
        OUTBOX_TABLE,
        metadata,
        Column("id", String(36), primary_key=True, comment="id do CloudEvent (chave de dedupe)"),
        Column("event_type", String(200), nullable=False),
        Column("event_hub", String(200), nullable=False),
        Column("aggregate_id", String(100), nullable=False, comment="chave de partição"),
        Column("aggregate_version", Integer, nullable=False),
        Column("payload", JSON, nullable=False, comment="CloudEvent completo"),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("published_at", DateTime(timezone=True), nullable=True, index=True),
        Column("attempts", Integer, nullable=False, default=0),
        Column("last_error", Text, nullable=True),
    )


def add_to_outbox(
    session: Session,
    table: Table,
    event: CloudEvent,
    validator: SchemaValidator | None = None,
) -> None:
    """Valida (opcional, recomendado) e grava o evento na transação corrente da ``session``."""
    if validator is not None:
        validator.validate(event)
    session.execute(
        table.insert().values(
            id=event.id,
            event_type=event.type,
            event_hub=event.event_hub,
            aggregate_id=event.aggregateid,
            aggregate_version=event.aggregateversion,
            payload=event.to_dict(),
            created_at=datetime.now(UTC),
            attempts=0,
        )
    )


class Publisher(Protocol):
    def publish(self, event_hub: str, partition_key: str, body: str) -> None: ...


class OutboxRelay:
    """Publica eventos pendentes da outbox. Use ``run_once`` em testes e ``run_forever`` no worker."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        table: Table,
        publisher: Publisher,
        batch_size: int = 100,
        poll_interval_seconds: float = 1.0,
    ):
        self._session_factory = session_factory
        self._table = table
        self._publisher = publisher
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds

    def run_once(self) -> int:
        """Publica um lote. Retorna quantos eventos foram publicados."""
        t = self._table
        published = 0
        with self._session_factory() as session, session.begin():
            rows = session.execute(
                select(t.c.id, t.c.event_hub, t.c.aggregate_id, t.c.payload)
                .where(t.c.published_at.is_(None))
                .order_by(t.c.created_at)
                .limit(self._batch_size)
                .with_for_update(skip_locked=True)
            ).all()

            for row in rows:
                body = CloudEvent.from_dict(row.payload).to_json()
                try:
                    self._publisher.publish(row.event_hub, row.aggregate_id, body)
                except Exception as exc:  # noqa: BLE001 - registra e tenta no próximo ciclo
                    log.warning("Falha ao publicar %s: %s", row.id, exc)
                    session.execute(
                        update(t).where(t.c.id == row.id)
                        .values(attempts=t.c.attempts + 1, last_error=str(exc)[:2000])
                    )
                    # Mantém a ordem por agregado: para no primeiro erro do lote.
                    break
                session.execute(
                    update(t).where(t.c.id == row.id)
                    .values(published_at=datetime.now(UTC), attempts=t.c.attempts + 1, last_error=None)
                )
                published += 1
        return published

    def run_forever(self, should_stop: Callable[[], bool] = lambda: False) -> None:
        log.info("Outbox relay iniciado (lote=%d)", self._batch_size)
        while not should_stop():
            try:
                count = self.run_once()
            except Exception:  # noqa: BLE001 - banco indisponível etc.; tenta de novo
                log.exception("Erro no ciclo do relay")
                count = 0
            if count:
                log.info("Publicados %d eventos", count)
            else:
                time.sleep(self._poll_interval)
