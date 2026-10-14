"""Convenções de nomes de eventos (ADR-0008).

Tipo do evento (atributo ``type`` do CloudEvents):  ``<dominio>.<agregado>.<evento>.v<major>``
Event hub (um por agregado e versão major):        ``<dominio>.<agregado>.v<major>``
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TYPE_RE = re.compile(r"^(?P<domain>[a-z][a-z0-9]*)\.(?P<aggregate>[a-z][a-z0-9_]*)\."
                      r"(?P<event>[a-z][a-z0-9_]*)\.v(?P<major>[1-9][0-9]*)$")

# Sufixos que denunciam eventos CRUD em vez de fatos de negócio (lint da plataforma).
_GENERIC_EVENTS = {"atualizado", "alterado", "modificado", "updated", "changed", "modified"}


@dataclass(frozen=True)
class EventType:
    domain: str
    aggregate: str
    event: str
    major: int

    @classmethod
    def parse(cls, value: str) -> EventType:
        match = _TYPE_RE.match(value)
        if not match:
            raise ValueError(
                f"Tipo de evento inválido: {value!r}. Esperado <dominio>.<agregado>.<evento>.v<major>, "
                "em minúsculas (ex.: pedidos.pedido.criado.v1)."
            )
        if match["event"] in _GENERIC_EVENTS:
            raise ValueError(
                f"Evento genérico {match['event']!r} em {value!r}: publique o fato de negócio "
                "(ex.: pedido.cancelado), não uma mudança de linha."
            )
        return cls(match["domain"], match["aggregate"], match["event"], int(match["major"]))

    @property
    def event_hub(self) -> str:
        return f"{self.domain}.{self.aggregate}.v{self.major}"

    def __str__(self) -> str:
        return f"{self.domain}.{self.aggregate}.{self.event}.v{self.major}"


def event_hub_for(event_type: str) -> str:
    """Event hub onde o tipo de evento é publicado (um por agregado)."""
    return EventType.parse(event_type).event_hub
