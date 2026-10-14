"""Publisher em memória, para testes e execução local sem Azure."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PublishedMessage:
    event_hub: str
    partition_key: str
    body: str


@dataclass
class InMemoryPublisher:
    messages: list[PublishedMessage] = field(default_factory=list)
    fail_on: set[str] = field(default_factory=set)

    def publish(self, event_hub: str, partition_key: str, body: str) -> None:
        if partition_key in self.fail_on:
            raise ConnectionError(f"falha simulada para {partition_key}")
        self.messages.append(PublishedMessage(event_hub, partition_key, body))
