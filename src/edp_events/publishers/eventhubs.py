"""Publisher para Azure Event Hubs com Entra ID (Workload Identity no AKS). Sem SAS, sem segredos.

Usa o SDK AMQP (``azure-eventhub``), que autentica nativamente com ``DefaultAzureCredential``.
O endpoint Kafka do mesmo namespace continua disponível para consumidores (ex.: Spark).

- ``partition_key`` = id do agregado => ordem garantida por agregado (ADR-0008).
- Corpo = CloudEvent em structured mode; ``content_type`` = application/cloudevents+json.
  O Event Hubs Capture grava esse corpo no campo ``Body`` do Avro, que a Bronze decodifica.

Requer o extra ``eventhubs``: ``pip install "edp-events[eventhubs]"``.
"""

from __future__ import annotations

import atexit

from azure.eventhub import EventData, EventHubProducerClient
from azure.identity import DefaultAzureCredential

from edp_events.envelope import CONTENT_TYPE


class EventHubsPublisher:
    def __init__(self, fully_qualified_namespace: str, credential=None):
        self._namespace = fully_qualified_namespace
        self._credential = credential or DefaultAzureCredential()
        self._producers: dict[str, EventHubProducerClient] = {}
        atexit.register(self.close)

    def _producer(self, event_hub: str) -> EventHubProducerClient:
        if event_hub not in self._producers:
            self._producers[event_hub] = EventHubProducerClient(
                fully_qualified_namespace=self._namespace,
                eventhub_name=event_hub,
                credential=self._credential,
            )
        return self._producers[event_hub]

    def publish(self, event_hub: str, partition_key: str, body: str) -> None:
        event = EventData(body)
        event.content_type = CONTENT_TYPE
        self._producer(event_hub).send_event(event, partition_key=partition_key)

    def close(self) -> None:
        for producer in self._producers.values():
            producer.close()
        self._producers.clear()
