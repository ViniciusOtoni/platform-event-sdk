"""SDK de eventos da plataforma de dados event-driven.

- ``envelope``: CloudEvents 1.0 com as extensões da plataforma (ADR-0003).
- ``naming``: convenções de tipo de evento e event hub (ADR-0008).
- ``schema``: validação do payload por JSON Schema (ADR-0003 / ADR-0005).
- ``outbox``: Transactional Outbox, gravação na transação e relay (ADR-0002).
- ``publishers``: destino do relay (Event Hubs com Entra ID; memória para testes).
"""

from edp_events.envelope import CloudEvent, new_event
from edp_events.naming import EventType, event_hub_for
from edp_events.outbox import OutboxRelay, add_to_outbox, register_outbox
from edp_events.schema import SchemaValidationError, SchemaValidator

__all__ = [
    "CloudEvent",
    "EventType",
    "OutboxRelay",
    "SchemaValidationError",
    "SchemaValidator",
    "add_to_outbox",
    "event_hub_for",
    "new_event",
    "register_outbox",
]

__version__ = "0.1.0"
