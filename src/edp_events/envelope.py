"""Envelope CloudEvents 1.0 (structured mode, JSON) com as extensões da plataforma (ADR-0003).

Extensões:
- ``aggregateid``: id do agregado; também é a chave de partição no Event Hubs.
- ``aggregateversion``: versão do agregado após o evento; a Silver só aplica versões maiores.
- ``traceparent``: contexto W3C para rastreamento distribuído (opcional).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from edp_events.naming import EventType

SPEC_VERSION = "1.0"
CONTENT_TYPE = "application/cloudevents+json; charset=utf-8"


@dataclass(frozen=True)
class CloudEvent:
    type: str
    source: str
    subject: str
    aggregateid: str
    aggregateversion: int
    data: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    time: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds"))
    datacontenttype: str = "application/json"
    traceparent: str | None = None

    def __post_init__(self) -> None:
        EventType.parse(self.type)
        if self.aggregateversion < 1:
            raise ValueError("aggregateversion deve ser >= 1")

    @property
    def dataschema(self) -> str:
        return f"urn:schema:{self.type}"

    @property
    def event_hub(self) -> str:
        return EventType.parse(self.type).event_hub

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "specversion": SPEC_VERSION,
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "subject": self.subject,
            "time": self.time,
            "datacontenttype": self.datacontenttype,
            "dataschema": self.dataschema,
            "aggregateid": self.aggregateid,
            "aggregateversion": self.aggregateversion,
            "data": self.data,
        }
        if self.traceparent:
            body["traceparent"] = self.traceparent
        return body

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"), default=str)

    @classmethod
    def from_dict(cls, body: dict[str, Any]) -> CloudEvent:
        return cls(
            id=body["id"],
            type=body["type"],
            source=body["source"],
            subject=body["subject"],
            time=body["time"],
            datacontenttype=body.get("datacontenttype", "application/json"),
            aggregateid=body["aggregateid"],
            aggregateversion=int(body["aggregateversion"]),
            traceparent=body.get("traceparent"),
            data=body["data"],
        )


def new_event(
    *,
    type: str,
    source: str,
    aggregate: str,
    aggregate_id: str,
    aggregate_version: int,
    data: dict[str, Any],
    traceparent: str | None = None,
) -> CloudEvent:
    """Cria um evento de integração. ``subject`` segue ``<agregado>/<id>``."""
    return CloudEvent(
        type=type,
        source=source,
        subject=f"{aggregate}/{aggregate_id}",
        aggregateid=aggregate_id,
        aggregateversion=aggregate_version,
        data=data,
        traceparent=traceparent,
    )
